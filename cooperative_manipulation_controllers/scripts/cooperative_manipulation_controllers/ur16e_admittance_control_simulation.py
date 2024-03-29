#!/usr/bin/env python3

# /***************************************************************************

# **************************************************************************/

"""
    Description...
    
    Admittance controller
    
    Input: 
    * Desired cartesian velocity of the EE: desired_velocity (In 'world' frame)
    * External wrench from the f/t sensor: wrench_ext (In 'wrist_3_link' frame)
    
    Output: 
    * Target joint velocity: self.target_joint_velocity (In 'base_link' frame)
"""

from pickle import TRUE
import sys
import numpy, math
import rospy
import tf
from tf.transformations import quaternion_from_euler, euler_from_quaternion
import tf2_ros
import moveit_commander
from geometry_msgs.msg import WrenchStamped, Vector3Stamped, Twist, TransformStamped, PoseStamped
from std_msgs.msg import Float64MultiArray
from cooperative_manipulation_controllers.msg import SingularityAvoidance
import copy


class ur_admittance_controller():
    
    def config(self):
        # Stiffness gains
        self.P_trans_x = 5
        self.P_trans_y = 5
        self.P_trans_z = 5
        self.P_rot_x = 5
        self.P_rot_y = 5
        self.P_rot_z = 5
        # Damping gains
        self.D_trans_x = 5
        self.D_trans_y = 5
        self.D_trans_z = 5
        self.D_rot_x = 5
        self.D_rot_y = 5
        self.D_rot_z = 5
        
        self.world_z_vector = numpy.array([0.0,0.0,1.0])
        self.wrist_link_3_rot_axis = numpy.array([0.0,0.0,0.0])
        
        self.wrist_link_3_desired_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        
        
        # Min and max limits for the cartesian velocity (trans/rot) [m/s]
        self.cartesian_velocity_trans_min_limit = 0.0009
        self.cartesian_velocity_trans_max_limit = 0.1
        self.cartesian_velocity_rot_min_limit = 0.001
        self.cartesian_velocity_rot_max_limit = 0.1
        # Control thread publish rate [Hz]
        self.publish_rate = 100
        # Initialize wrench_ext_filtered
        self.wrench_force_filtered_x = 0.0
        self.wrench_force_filtered_y = 0.0
        self.wrench_force_filtered_z = 0.0
        # Wrench filter treshold (when not cooperative_manipulation: 0.05 - 0.1(cmd_vel: 0.8 or higher))
        self.wrench_filter = 0.1
        # 
        self.force_filter_factor = 140.0
        self.torque_filter_trans_factor = 10.9
        self.torque_filter_factor = 10.9

        
        
        self.force_filter_factor_array = numpy.array([0.0,0.0,0.0])
        self.torque_filter_factor_array = numpy.array([0.0,0.0,0.0,])

        self.average_filter_list_force_x = []
        self.average_filter_list_force_y = []
        self.average_filter_list_force_z = []
        self.average_filter_list_torque_x = []
        self.average_filter_list_torque_y = []
        self.average_filter_list_torque_z = []
        self.average_filter_list_length = 100

        self.average_force_x = 0.0
        self.average_force_y = 0.0
        self.average_force_z = 0.0
        self.average_torque_x = 0.0
        self.average_torque_y = 0.0
        self.average_torque_z = 0.0
        # Initialize trajectory velocity for object rotation
        self.world_trajectory_velocity = numpy.array([0.0,0.0,0.0])
        # The gripper offset
        self.r16e_gripper_offset_trans_z = 0.16163
        # * Initialize the needed velocity data types:
        # Initialize desired velocity transformed form 'wrorld' frame to 'base_link' frame (xdot_desired_baselink)
        self.base_link_desired_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.world_cartesian_velocity_trans = Vector3Stamped()
        self.world_cartesian_velocity_rot = Vector3Stamped()
        self.wrist_link_3_cartesian_desired_velocity_trans  = Vector3Stamped()
        self.wrist_link_3_cartesian_desired_velocity_rot  = Vector3Stamped()
        
        
        self.world_rot_velocity_cross_product_vector = Vector3Stamped()
        # Initialize velocity from admittance (xdot_a_wrist_3_link)
        self.admittance_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        # Initialize velocity from admittance 'wrist_3_link' frame to 'base_link' frame  (xdot_a_baselink)
        self.admittance_velocity_transformed  = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        # Initialize target cartesian velocity array (xdot_target_baselink)
        self.target_cartesian_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        # Declare target joint velocity msgs (qdot_target_baselink) (unit: [radian/s])
        self.target_joint_velocity = Float64MultiArray()
        # Initialize velocity (xdot_desired_wrist_3_link)
        self.velocity_transformed = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.wrist_3_link_cartesian_velocity_trans = Vector3Stamped()
        self.wrist_3_link_cartesian_velocity_rot = Vector3Stamped()
        # Initialize shutdown joint velocity, called on shutdown 
        self.shutdown_joint_velocity = Float64MultiArray()
        self.shutdown_joint_velocity.data = [0.0,0.0,0.0,0.0,0.0,0.0]
        # Declare the wrench variables
        self.wrench_ext_filtered = WrenchStamped()
        self.wrench_difference = WrenchStamped()        
        self.wrench_ext_filtered_trans_array = numpy.array([])
        self.wrench_ext_filtered_rot_array = numpy.array([])
        #* Singulariy avoidance: OLMM
        self.singularity_velocity_world = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        
        self.singularity_stop = False
        self.singularity_entry_threshold = 0.05
        self.singularity_min_threshold = 0.01
        self.adjusting_scalar = 0.0
        self.singularity_velocity_cmd = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.singularity_avoidance_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.singularity_velocity_msg = SingularityAvoidance()
        self.bool_singularity = False
        self.bool_reduce_singularity_offset = False
        self.singularity_trans_offset_accuracy = 0.001 # [m]
        self.singularity_rot_offset_accuracy = 0.0174 # [rad] ~ 1 [°]
        self.last_target_trans_cartesian_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0]) 
        self.last_target_rot_cartesian_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0]) 
        # Trajectory
        self.base_link_trajectory_pose_array  = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
               
        self.target_cartesian_velocity_new = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.target_cartesian_velocity_old  = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])

        self.bool_test = False
        
        self.last_target_trans_cartesian_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0]) 
        self.last_target_rot_cartesian_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0]) 

        

        
        
    def __init__(self):
        # * Load config parameters
        self.config()
        
        # * Initialize node
        rospy.init_node('admittance_controller_node', anonymous=True)
        
        # * Initialize on_shutdown clean up
        rospy.on_shutdown(self.shutdown)

        # * Initialize tf TransformBroadcaster
        self.brodacaster = tf2_ros.StaticTransformBroadcaster()
        # * Initialize tf transformations
        self.tf_transformatios = tf.transformations
        # * Initialize tf TransformListener
        self.tf_listener = tf.TransformListener()
        rospy.loginfo("Wait for transformation 'wrist_3_link' to 'base_link'.")
        self.tf_listener.waitForTransform("wrist_3_link","base_link", rospy.Time(), rospy.Duration(5.0))
        rospy.loginfo("Wait for transformation 'world' to 'wrist_3_link'.")
        self.tf_listener.waitForTransform("world","wrist_3_link", rospy.Time(), rospy.Duration(5.0))
        rospy.loginfo("Wait for transformation 'world' to 'base_link'.")
        self.tf_listener.waitForTransform("world","base_link", rospy.Time(), rospy.Duration(5.0))
        
        # Initialize the 'ur16e_gripper' frame in tf tree
        self.set_gripper_offset()
        # Wait for transformations from 'world' to 'ur16e_gripper' and 'world' to 'panda_gripper'
        rospy.loginfo("Wait for transformation 'world' to 'ur16e_gripper'.")
        self.tf_listener.waitForTransform("world","ur16e_gripper", rospy.Time(), rospy.Duration(10.0))
        # rospy.loginfo("Wait for transformation 'world' to '/panda/panda_link8'.")
        # self.tf_listener.waitForTransform("world","panda/panda_link8", rospy.Time(), rospy.Duration(10.0))

        # * Get namespace for topics from launch file
        self.namespace = rospy.get_param("~ur_ns")
        
        # * Initialize move_it
        moveit_commander.roscpp_initialize(sys.argv)
        
        try:
            group_name = 'manipulator'
            print("Initialize movit_commander. Group name: ",group_name)
            self.group = moveit_commander.MoveGroupCommander(group_name, wait_for_servers=5.0)
        except Exception as e: 
            print(e)
        
        # * Initialize publisher:
        # Publish final joint velocity to "/ur/ur_admittance_controller/command"
        self.joint_velocity_pub = rospy.Publisher(
            "/" + self.namespace + "/ur_admittance_controller/command",
            Float64MultiArray,
            queue_size=1)
        
        # Publish singularity velocity
        self.singularity_velocity_pub = rospy.Publisher(
            "/cooperative_manipulation/ur16e/singularity_velocity",
            SingularityAvoidance,
            queue_size=1)
        
        # Publish final joint velocity to "/ur/ur_admittance_controller/command"
        self.wrench_filter_pub = rospy.Publisher(
            "/" + self.namespace + "/ur_admittance_controller/wrench_filter",
            WrenchStamped,
            queue_size=1)
        
        # * Initialize subscriber:
        # Subscriber to "/ur/wrench"
        self.wrench_ext_sub = rospy.Subscriber(
            "/" + self.namespace + "/ft_sensor/raw",
            WrenchStamped,
            self.wrench_callback,queue_size=1)
        
        # Subscriber to "/ur/cooperative_manipulation/cartesian_velocity_command"
        self.cartesian_velocity_command_sub = rospy.Subscriber(
            "/cooperative_manipulation/cartesian_velocity_command",
            Twist,
            self.cartesian_velocity_command_callback,queue_size=1)
        
        self.cartesian_velocity_command_sub = rospy.Subscriber(
            "/cooperative_manipulation/world_trajectory",
            Float64MultiArray,
            self.world_trajectory_callback,queue_size=1)
        
        
        
        
        
        
        
        
        
        
        
        
        # Wait for messages to be populated before proceeding
        rospy.wait_for_message("/" + self.namespace + "/ft_sensor/raw",WrenchStamped,timeout=5.0)
        
        
        rospy.loginfo("Recieved messages; Launch ur16e Admittance control.")
        
        
        
        # * Get the start EE pose
        start_world_EE_pose = self.group.get_current_pose('wrist_3_link')
        print(start_world_EE_pose)
        start_world_EE_pose_quaternion = (start_world_EE_pose.pose.orientation.x,
                                        start_world_EE_pose.pose.orientation.y,
                                        start_world_EE_pose.pose.orientation.z,
                                        start_world_EE_pose.pose.orientation.w)
        
        start_world_EE_pose_euler = euler_from_quaternion(start_world_EE_pose_quaternion)
        
        self.start_world_EE_pose_pose_array = numpy.array([start_world_EE_pose.pose.position.x,
                                            start_world_EE_pose.pose.position.y,
                                            start_world_EE_pose.pose.position.z,
                                            start_world_EE_pose_euler[0],
                                            start_world_EE_pose_euler[1],
                                            start_world_EE_pose_euler[2]])
                
        self.current_EE_pose = self.pose_stamped_transformation('world','base_link',self.start_world_EE_pose_pose_array ) 
        
        rospy.loginfo('world')
        rospy.loginfo(self.start_world_EE_pose_pose_array)
        rospy.loginfo('base_link')
        rospy.loginfo(self.current_EE_pose)
            
        
        # * Run control_thread
        self.control_thread()
        
        rospy.spin()
        
    def set_gripper_offset(self):
        """
            Set the gripper offset from 'wirst_3_link' frame.
        """
        static_gripper_offset = TransformStamped()
        static_gripper_offset.header.stamp = rospy.Time.now()
        static_gripper_offset.header.frame_id = "wrist_3_link"
        static_gripper_offset.child_frame_id = "ur16e_gripper"
        static_gripper_offset.transform.translation.x = 0.0
        static_gripper_offset.transform.translation.y = 0.0
        static_gripper_offset.transform.translation.z = self.r16e_gripper_offset_trans_z
        static_gripper_offset.transform.rotation.x = 0.0
        static_gripper_offset.transform.rotation.y = 0.0
        static_gripper_offset.transform.rotation.z = 0.0
        static_gripper_offset.transform.rotation.w = 1.0

        self.brodacaster.sendTransform(static_gripper_offset)
        
            
            
    def scalar_adjusting_function(self,current_sigma,):
        """Compute the adjusting scalar for the OLMM. 3 varaitions to calculate the adjusting scalar are presented.

            Source: QIU, Changwu; CAO, Qixin; MIAO, Shouhong. An on-line task modification method for singularity avoidance of robot manipulators. Robotica, 2009, 27. Jg., Nr. 4, S. 539-546.

        Args:
            current_sigma (float): The current singular value

        Returns:
            float: The adjusting_scalar
        """
        
        
        # 0.
        # adjusting_scalar = (1-current_sigma)
        # 1.
        # adjusting_scalar = (1-(current_sigma/self.singularity_entry_threshold))
        # 2.
        # adjusting_scalar = (1-(current_sigma/self.singularity_entry_threshold)**(1/2))
        # 3.
        adjusting_scalar = (1-(current_sigma/self.singularity_entry_threshold)**(3/2))
        
        return adjusting_scalar
    
    def compute_rotation_trajectory_velocity(self,rotation_center: numpy.array,desired_angular_velocity: numpy.array, target_frame: str, EE_frame: str):
        """_summary_

        Args:
            rotation_center (numpy.array): _description_
            desired_angular_velocity (numpy.array): _description_
            target_frame (str): _description_
            EE_frame (str): _description_
        """
         # Get current time stamp
        now = rospy.Time()
        
        # print("desired_angular_velocity")
        # print(desired_angular_velocity)
    
        # Calculate the trajectory velocity of the manipulator for a rotation of the object
        # Get ur16e_current_position, ur16e_current_quaternion of the 'wrist_3_link' in frame in the 'world' frame 
        EE_tf_time = self.tf_listener.getLatestCommonTime(target_frame, EE_frame)
        EE_current_position, EE_current_quaternion = self.tf_listener.lookupTransform(target_frame, EE_frame, EE_tf_time)
        
        world_trajectory_velocity = numpy.array([0.0,0.0,0.0])
        # Object rotation around x axis 
        if desired_angular_velocity[0] != 0.0:
            EE_current_position_x = numpy.array([
                0.0,
                EE_current_position[1],
                EE_current_position[2]
                ])
            
            rotation_center_x = numpy.array([0.0,rotation_center[1],rotation_center[2]])

            world_desired_rotation_x = numpy.array([desired_angular_velocity[0],0.0,0.0])
            world_radius_x = EE_current_position_x - rotation_center_x
            world_trajectory_velocity_x = numpy.cross(world_desired_rotation_x,world_radius_x)
            world_trajectory_velocity = world_trajectory_velocity + world_trajectory_velocity_x
            
        # Object rotation around y axis 
        if desired_angular_velocity[1] != 0.0:
            EE_current_position_y = numpy.array([
                EE_current_position[1],
                0.0,
                EE_current_position[2]
                ])
            
            rotation_center_y = numpy.array([rotation_center[0],0.0,rotation_center[2]])

            world_desired_rotation_y = numpy.array([0.0,desired_angular_velocity[1],0.0])
            world_radius_y = EE_current_position_y - rotation_center_y
            world_trajectory_velocity_y = numpy.cross(world_desired_rotation_y,world_radius_y)
            world_trajectory_velocity = world_trajectory_velocity + world_trajectory_velocity_y
        
         # Object rotation around z axis 
        if desired_angular_velocity[2] != 0.0:
            EE_current_position_z = numpy.array([
                EE_current_position[0],
                EE_current_position[1],
                0.0
                ])
            
            rotation_center_z = numpy.array([rotation_center[0],rotation_center[1],0.0])

            world_desired_rotation_z = numpy.array([0.0,0.0,desired_angular_velocity[2]])
            world_radius_z = EE_current_position_z - rotation_center_z
            world_trajectory_velocity_z = numpy.cross(world_desired_rotation_z,world_radius_z)
            world_trajectory_velocity = world_trajectory_velocity + world_trajectory_velocity_z
        
        return world_trajectory_velocity
    
    def pose_stamped_transformation(self,source_frame: str,target_frame: str,input_array: numpy.array):
        """ Transform a PoseStamped array from the source frame to the target frame with euler angles.

        Args:
            source_frame (str): _description_
            target_frame (str): _description_
            input_array (numpy.array): _description_

        Returns:
            numpy.array: _
        """
        now = rospy.Time()
        
        source_position = PoseStamped()
        source_position.header.frame_id = source_frame
        source_position.header.stamp = now
        source_position.pose.position.x = input_array[0]
        source_position.pose.position.y = input_array[1]
        source_position.pose.position.z = input_array[2]
        
        source_frame_quaternion = quaternion_from_euler(input_array[3],input_array[4],input_array[5])
                
        source_position.pose.orientation.x = source_frame_quaternion[0]
        source_position.pose.orientation.y = source_frame_quaternion[1]
        source_position.pose.orientation.z = source_frame_quaternion[2]
        source_position.pose.orientation.w = source_frame_quaternion[3]
        
        target_frame_position = self.tf_listener.transformPose(target_frame,source_position)
        
        target_frame_quaternion =  (target_frame_position.pose.orientation.x,
                                    target_frame_position.pose.orientation.y,
                                    target_frame_position.pose.orientation.z,
                                    target_frame_position.pose.orientation.w)
        
        target_frame_euler = euler_from_quaternion(target_frame_quaternion)
        
        output_array = numpy.array([target_frame_position.pose.position.x,
                                    target_frame_position.pose.position.y,
                                    target_frame_position.pose.position.z,
                                    target_frame_euler[0],
                                    target_frame_euler[1],
                                    target_frame_euler[2]])  
        return output_array
        
    
    def world_trajectory_callback(self,world_trajectory_msg):
        """_summary_
        """
        worl_current_EE_pose = self.start_world_EE_pose_pose_array + world_trajectory_msg.data
        
        # self.current_EE_pose = self.pose_stamped_transformation('world','base_link',worl_current_EE_pose) 


    def cartesian_velocity_command_callback(self,desired_velocity):
        """
            Get the cartesian velocity command and transform it from from the 'world' frame to the 'base_link' and 'wrist_link_3' frame.
            
            Send example velocity:
            rostopic pub -r 10 cooperative_manipulation/cartesian_velocity_command geometry_msgs/Twist "linear:
            x: 0.0
            y: 0.0
            z: 0.0
            angular:
            x: 0.0
            y: 0.0
            z: 0.0" 
        """
        # print("desired_velocity")
        # print(desired_velocity)
        
        # ToDo ------------------------------------------------------------------
        
        # Get current time stamp
        now = rospy.Time()
        
        # print("desired_velocity")
        # print(desired_velocity)
    
        # Calculate the trajectory velocity of the manipulator for a rotation of the object
        # Get ur16e_current_position, ur16e_current_quaternion of the 'wrist_3_link' in frame in the 'world' frame 
        ur16e_tf_time = self.tf_listener.getLatestCommonTime("/world", "/wrist_3_link")
        ur16e_current_position, ur16e_current_quaternion = self.tf_listener.lookupTransform("/world", "/wrist_3_link", ur16e_tf_time)

        # Get ur16e_current_position, ur16e_current_quaternion of the 'ur16e_gripper' in frame in the 'world' frame 
        ur16e_tf_time = self.tf_listener.getLatestCommonTime("/world", "/ur16e_gripper")
        ur16e_gripper_position, ur16e_gripper_quaternion = self.tf_listener.lookupTransform("/world", "/ur16e_gripper", ur16e_tf_time)

        # Get self.panda_current_position, self.panda_current_quaternion of the '/panda/panda_link8' frame in the 'world' frame 
        panda_tf_time = self.tf_listener.getLatestCommonTime("/world", "/panda/panda_link8")
        panda_gripper_position, panda_gripper_quaternion = self.tf_listener.lookupTransform("/world", "/panda/panda_gripper", panda_tf_time)

        # print("self.ur16e_current_position, self.ur16e_current_quaternion")
        # print(self.ur16e_current_position, self.ur16e_current_quaternion)
        # print("self.panda_current_position, self.panda_current_quaternion")
        # print(self.panda_position, self.panda_current_quaternion)
        self.world_trajectory_velocity = [0.0,0.0,0.0]
        # Object rotation around x axis 
        if desired_velocity.angular.x != 0.0:
            ur16e_current_position_x = numpy.array([
                0.0,
                ur16e_current_position[1],
                ur16e_current_position[2]
                ])
            
            self.robot_distance_x = numpy.array([
                0.0,
                panda_gripper_position[1] - ur16e_gripper_position[1],
                panda_gripper_position[2] - ur16e_gripper_position[2],
            ])
            
            center_x = (numpy.linalg.norm(self.robot_distance_x)/2) * (1/numpy.linalg.norm(self.robot_distance_x)) * self.robot_distance_x + ur16e_gripper_position
            world_desired_rotation_x = numpy.array([desired_velocity.angular.x,0.0,0.0])
            world_radius_x = ur16e_current_position_x - center_x
            self.world_trajectory_velocity_x = numpy.cross(world_desired_rotation_x,world_radius_x)
            self.world_trajectory_velocity = self.world_trajectory_velocity + self.world_trajectory_velocity_x
            
        # Object rotation around y axis 
        if desired_velocity.angular.y != 0.0: 
            ur16e_current_position_y = numpy.array([
                ur16e_current_position[0],
                0.0,
                ur16e_current_position[2]
                ]) 
            
            self.robot_distance_y = numpy.array([
                panda_gripper_position[0] - ur16e_gripper_position[0],
                0.0,
                panda_gripper_position[2] - ur16e_gripper_position[2],
                ])
            
            center_y = (numpy.linalg.norm(self.robot_distance_y)/2) * (1/numpy.linalg.norm(self.robot_distance_y)) * self.robot_distance_y + ur16e_gripper_position
            world_desired_rotation_y = numpy.array([0.0,desired_velocity.angular.y,0.0])
            world_radius_y = ur16e_current_position_y - center_y
            self.world_trajectory_velocity_y = numpy.cross(world_desired_rotation_y,world_radius_y)
            self.world_trajectory_velocity = self.world_trajectory_velocity + self.world_trajectory_velocity_y 

        # Object rotation around z axis 
        if desired_velocity.angular.z != 0.0:
            ur16e_current_position_z = numpy.array([
                ur16e_current_position[0],
                ur16e_current_position[1],
                0.0,
                ]) 
                            
            self.robot_distance_z = numpy.array([
                panda_gripper_position[0] - ur16e_gripper_position[0],
                panda_gripper_position[1] - ur16e_gripper_position[1],
                0.0,
                ])
            
            
            center_z = (numpy.linalg.norm(self.robot_distance_z)/2) * (1/numpy.linalg.norm(self.robot_distance_z)) * self.robot_distance_z + ur16e_gripper_position
            world_desired_rotation_z = numpy.array([0.0,0.0,desired_velocity.angular.z])
            world_radius_z = ur16e_current_position_z - center_z
            self.world_trajectory_velocity_z = numpy.cross(world_desired_rotation_z,world_radius_z)
            self.world_trajectory_velocity = self.world_trajectory_velocity + self.world_trajectory_velocity_z 


        # ToDo ------------------------------------------------------------------
        
        # Get current time stamp
        now = rospy.Time()

        # Converse cartesian_velocity translation to vector3
        self.world_cartesian_velocity_trans.header.frame_id = 'world'
        self.world_cartesian_velocity_trans.header.stamp = now
        self.world_cartesian_velocity_trans.vector.x = desired_velocity.linear.x + self.world_trajectory_velocity[0]
        self.world_cartesian_velocity_trans.vector.y = desired_velocity.linear.y + self.world_trajectory_velocity[1]
        self.world_cartesian_velocity_trans.vector.z = desired_velocity.linear.z + self.world_trajectory_velocity[2]
        
        # Transform cartesian_velocity translation from 'world' frame to 'base_link' frame
        self.base_link_cartesian_desired_velocity_trans = self.tf_listener.transformVector3('base_link',self.world_cartesian_velocity_trans)
        
        
        # Converse cartesian_velocity rotation to vector3
        self.world_cartesian_velocity_rot.header.frame_id = 'world'
        self.world_cartesian_velocity_rot.header.stamp = now
        self.world_cartesian_velocity_rot.vector.x = desired_velocity.angular.x
        self.world_cartesian_velocity_rot.vector.y = desired_velocity.angular.y
        self.world_cartesian_velocity_rot.vector.z = desired_velocity.angular.z
        
        # Transform cartesian_velocity rotation from 'world' frame to 'base_link' frame
        self.base_link_cartesian_desired_velocity_rot = self.tf_listener.transformVector3('base_link',self.    world_cartesian_velocity_rot)
        
        # Converse cartesian_velocity from vector3 to numpy.array
        self.base_link_desired_velocity = [
            self.base_link_cartesian_desired_velocity_trans.vector.x,
            self.base_link_cartesian_desired_velocity_trans.vector.y,
            self.base_link_cartesian_desired_velocity_trans.vector.z,
            self.base_link_cartesian_desired_velocity_rot.vector.x,
            self.base_link_cartesian_desired_velocity_rot.vector.y,
            self.base_link_cartesian_desired_velocity_rot.vector.z
            ]
        

        
        self.world_desired_velocity = [
            self.world_cartesian_velocity_trans.vector.x,
            self.world_cartesian_velocity_trans.vector.y,
            self.world_cartesian_velocity_trans.vector.z
            ]
        

        
        # Transform cartesian_velocity rotation from 'world' frame to 'wrist_3_link' frame
        self.wrist_link_3_cartesian_desired_velocity_trans = self.tf_listener.transformVector3('wrist_3_link',self.world_cartesian_velocity_trans)
        
        # Transform cartesian_velocity rotation from 'world' frame to 'wrist_3_link' frame
        self.wrist_link_3_cartesian_desired_velocity_rot = self.tf_listener.transformVector3('wrist_3_link',self.world_cartesian_velocity_trans)
        
        self.wrist_link_3_desired_velocity = [
            self.wrist_link_3_cartesian_desired_velocity_trans.vector.x,
            self.wrist_link_3_cartesian_desired_velocity_trans.vector.y,
            self.wrist_link_3_cartesian_desired_velocity_trans.vector.z,
            self.wrist_link_3_cartesian_desired_velocity_rot.vector.x,
            self.wrist_link_3_cartesian_desired_velocity_rot.vector.y,
            self.wrist_link_3_cartesian_desired_velocity_rot.vector.z
            ]
        
        
        # print("self.wrist_link_3_desired_velocity")
        # print(self.wrist_link_3_desired_velocity )
        
        self.world_rot_velocity_cross_product_array = numpy.cross(self.world_desired_velocity,self.world_z_vector)
        
        # print("self.world_rot_velocity_cross_product_array")
        # print(self.world_rot_velocity_cross_product_array)
        
        # Converse self.world_rot_velocity_cross_product_array rotation to vector3
        self.world_rot_velocity_cross_product_vector.header.frame_id = 'world'
        self.world_rot_velocity_cross_product_vector.header.stamp = now
        self.world_rot_velocity_cross_product_vector.vector.x = self.world_rot_velocity_cross_product_array[0]
        self.world_rot_velocity_cross_product_vector.vector.y = self.world_rot_velocity_cross_product_array[1]
        self.world_rot_velocity_cross_product_vector.vector.z = self.world_rot_velocity_cross_product_array[2]
        
        
        # Transform cartesian_velocity rotation from 'world' frame to 'wrist_3_link' frame
        self.wrist_link_3_rot_axis_vector = self.tf_listener.transformVector3('wrist_3_link',self.world_rot_velocity_cross_product_vector)
        
        self.wrist_link_3_rot_axis = [
            self.wrist_link_3_rot_axis_vector.vector.x,
            self.wrist_link_3_rot_axis_vector.vector.y,
            self.wrist_link_3_rot_axis_vector.vector.z
            ]
        
        # print("self.wrist_link_3_rot_axis")
        # print(self.wrist_link_3_rot_axis)
    
    def wrench_callback(self,wrench_ext):
        """ 
            Get external wrench in wrist_link_3.
            
            Send example wrench:
            rostopic pub  /ur/wrench geometry_msgs/WrenchStamped '{header: {stamp: now, frame_id: base_link}, wrench:{force: {x: 0.0, y: 0.0, z: 0.0}, torque: {x: 0.0, y: 0.0, z: 0.0}}}'
        """
    
        # print("wrench_ext.wrench before filtered:")
        # print(wrench_ext.wrench)
        
        
        for f in range(3):
            if self.wrist_link_3_desired_velocity[f] != 0.0:
                # self.force_filter_factor = 141
                self.force_filter_factor_array[f] = self.force_filter_factor * numpy.abs(self.wrist_link_3_desired_velocity[f])   
            else:
                self.force_filter_factor_array[f] = 0.0
            
            if self.wrist_link_3_rot_axis[f]!= 0.0:
                # self.torque_filter_trans_factor = 10.9
                self.torque_filter_factor_array[f] = self.torque_filter_trans_factor * numpy.abs(self.wrist_link_3_rot_axis[f])
                
                if f == 3:
                    self.torque_filter_factor_array[f] = self.torque_filter_factor_z * numpy.abs(self.wrist_link_3_rot_axis[f])
            else:
                self.torque_filter_factor_array[f] = 0.0


        # for f in range(3,6):
        #     if self.desired_velocity_wrist_link_3[f] != 0.0:
        #         self.torque_filter_factor_array[f] = self.torque_filter_factor_array[f] + self.torque_filter_factor * numpy.abs(self.desired_velocity_wrist_link_3[f])
        #     else:
        #         self.ftorque_filter_factor_array[f] = 0.0

        # print("self.force_filter_factor_array:")
        # print(self.force_filter_factor_array)

        # print("self.torque_filter_factor_array:")
        # print(self.torque_filter_factor_array)

        # * Average filter
        # Fill the empty lists with wrench values
        if len(self.average_filter_list_force_x) < self.average_filter_list_length:
            # 2. Add the new wrench to the list 
            self.average_filter_list_force_x.append(wrench_ext.wrench.force.x - numpy.sign(wrench_ext.wrench.force.x) * self.force_filter_factor_array[0])
            self.average_filter_list_force_y.append(wrench_ext.wrench.force.y - numpy.sign(wrench_ext.wrench.force.y) *  self.force_filter_factor_array[1])
            self.average_filter_list_force_z.append(wrench_ext.wrench.force.z - numpy.sign(wrench_ext.wrench.force.z) *  self.force_filter_factor_array[2])
            self.average_filter_list_torque_x.append(wrench_ext.wrench.torque.x - numpy.sign(wrench_ext.wrench.torque.x) * self.torque_filter_factor_array[0])
            self.average_filter_list_torque_y.append(wrench_ext.wrench.torque.y - numpy.sign(wrench_ext.wrench.torque.y) *  self.torque_filter_factor_array[1])
            self.average_filter_list_torque_z.append(wrench_ext.wrench.torque.z - numpy.sign(wrench_ext.wrench.torque.z) *  self.torque_filter_factor_array[2])
            # 3. Calculate the average 
            self.average_force_x = sum(self.average_filter_list_force_x)/len(self.average_filter_list_force_x)
            self.average_force_y = sum(self.average_filter_list_force_y)/len(self.average_filter_list_force_y)
            self.average_force_z = sum(self.average_filter_list_force_z)/len(self.average_filter_list_force_z)
            self.average_torque_x = sum(self.average_filter_list_torque_x)/len(self.average_filter_list_torque_x)
            self.average_torque_y = sum(self.average_filter_list_torque_y)/len(self.average_filter_list_torque_y)
            self.average_torque_z = sum(self.average_filter_list_torque_z)/len(self.average_filter_list_torque_z)
            
        # If the lists reached the length of self.average_filter_list_length
        elif len(self.average_filter_list_force_x) == self.average_filter_list_length:
            # 1. Delete the first element in the list 
            self.average_filter_list_force_x.pop(0)
            self.average_filter_list_force_y.pop(0)
            self.average_filter_list_force_z.pop(0)
            self.average_filter_list_torque_x.pop(0)
            self.average_filter_list_torque_y.pop(0)
            self.average_filter_list_torque_z.pop(0)
            # 2. Add the new wrench to the list 
            self.average_filter_list_force_x.append(wrench_ext.wrench.force.x - numpy.sign(wrench_ext.wrench.force.x) * self.force_filter_factor_array[0])
            self.average_filter_list_force_y.append(wrench_ext.wrench.force.y - numpy.sign(wrench_ext.wrench.force.y) *  self.force_filter_factor_array[1])
            self.average_filter_list_force_z.append(wrench_ext.wrench.force.z - numpy.sign(wrench_ext.wrench.force.z) *  self.force_filter_factor_array[2])
            self.average_filter_list_torque_x.append(wrench_ext.wrench.torque.x - numpy.sign(wrench_ext.wrench.torque.x) * self.torque_filter_factor_array[0])
            self.average_filter_list_torque_y.append(wrench_ext.wrench.torque.y - numpy.sign(wrench_ext.wrench.torque.y) *  self.torque_filter_factor_array[1])
            self.average_filter_list_torque_z.append(wrench_ext.wrench.torque.z - numpy.sign(wrench_ext.wrench.torque.z) *  self.torque_filter_factor_array[2])
            # 3. Calculate the average 
            self.average_force_x = sum(self.average_filter_list_force_x)/self.average_filter_list_length
            self.average_force_y = sum(self.average_filter_list_force_y)/self.average_filter_list_length
            self.average_force_z = sum(self.average_filter_list_force_z)/self.average_filter_list_length
            self.average_torque_x = sum(self.average_filter_list_torque_x)/self.average_filter_list_length
            self.average_torque_y = sum(self.average_filter_list_torque_y)/self.average_filter_list_length
            self.average_torque_z = sum(self.average_filter_list_torque_z)/self.average_filter_list_length
            
            
        # print("self.average_force_x:")
        # print(self.average_force_x)
        # print("self.average_force_y:")
        # print(self.average_force_y)
        # print("self.average_force_z:")
        # print(self.average_force_z)
        
        # print("self.average_torque_x:")
        # print(self.average_torque_x)
        # print("self.average_torque_y:")
        # print(self.average_torque_y)
        # print("self.average_torque_z:")
        # print(self.average_torque_z)
        
        # * Band-passfilter
        if numpy.abs(self.average_force_x) < self.wrench_filter:
            self.wrench_ext_filtered.wrench.force.x = 0.0
        else: 
            self.wrench_ext_filtered.wrench.force.x = self.average_force_x - numpy.sign(self.average_force_x) * self.wrench_filter
            
        if(numpy.abs(self.average_force_y) < self.wrench_filter):
            self.wrench_ext_filtered.wrench.force.y = 0.0
        else: 
            self.wrench_ext_filtered.wrench.force.y = self.average_force_y - numpy.sign(self.average_force_y) * self.wrench_filter

        if(numpy.abs(self.average_force_z) < self.wrench_filter):
            self.wrench_ext_filtered.wrench.force.z = 0.0
        else: 
           self.wrench_ext_filtered.wrench.force.z = self.average_force_z - numpy.sign(self.average_force_z) * self.wrench_filter
           
        if(numpy.abs(self.average_torque_x) < self.wrench_filter):
            self.wrench_ext_filtered.wrench.torque.x = 0.0
        else: 
            self.wrench_ext_filtered.wrench.torque.x = self.average_torque_x - numpy.sign(self.average_torque_x) * self.wrench_filter
            
        if(numpy.abs(self.average_torque_y) < self.wrench_filter):
            self.wrench_ext_filtered.wrench.torque.y = 0.0
        else: 
            self.wrench_ext_filtered.wrench.torque.y = self.average_torque_y - numpy.sign(self.average_torque_y) * self.wrench_filter
        if(numpy.abs(self.average_torque_z) < self.wrench_filter):
            self.wrench_ext_filtered.wrench.torque.z = 0.0
        else: 
            self.wrench_ext_filtered.wrench.torque.z = self.average_torque_z - numpy.sign(self.average_torque_z) * self.wrench_filter
            
            
        # print("self.wrench_ext_filtered")
        # print(self.wrench_ext_filtered)
        self.wrench_filter_pub.publish(self.wrench_ext_filtered) 
    
    def transform_velocity(self,cartesian_velocity):
        """ 
            Transform the cartesian velocity from the 'wrist_3_link' frame to the 'base_link' frame.
        """
        # Get current time stamp
        now = rospy.Time()

        # Converse cartesian_velocity translation from numpy.array to vector3
        self.wrist_3_link_cartesian_velocity_trans.header.frame_id = 'wrist_3_link'
        self.wrist_3_link_cartesian_velocity_trans.header.stamp = now
        self.wrist_3_link_cartesian_velocity_trans.vector.x = cartesian_velocity[0]
        self.wrist_3_link_cartesian_velocity_trans.vector.y = cartesian_velocity[1]
        self.wrist_3_link_cartesian_velocity_trans.vector.z = cartesian_velocity[2]
        
        # Transform cartesian_velocity translation from 'wrist_3_link' frame to 'base_link' frame
        self.base_link_cartesian_velocity_trans = self.tf_listener.transformVector3('base_link',self.wrist_3_link_cartesian_velocity_trans)
        
        # Converse cartesian_velocity rotation from numpy.array to vector3
        self.wrist_3_link_cartesian_velocity_rot.header.frame_id = 'wrist_3_link'
        self.wrist_3_link_cartesian_velocity_rot.header.stamp = now
        self.wrist_3_link_cartesian_velocity_rot.vector.x = cartesian_velocity[3]
        self.wrist_3_link_cartesian_velocity_rot.vector.y = cartesian_velocity[4]
        self.wrist_3_link_cartesian_velocity_rot.vector.z = cartesian_velocity[5]
        
        # Transform cartesian_velocity rotation from 'wrist_3_link' frame to 'base_link' frame
        self.base_link_cartesian_velocity_rot = self.tf_listener.transformVector3('base_link',self.    wrist_3_link_cartesian_velocity_rot)
        
        # Converse cartesian_velocity from vector3 to numpy.array
        self.velocity_transformed = numpy.array([
            self.base_link_cartesian_velocity_trans.vector.x,
            self.base_link_cartesian_velocity_trans.vector.y,
            self.base_link_cartesian_velocity_trans.vector.z,
            self.base_link_cartesian_velocity_rot.vector.x,
            self.base_link_cartesian_velocity_rot.vector.y,
            self.base_link_cartesian_velocity_rot.vector.z
            ])
        
        return self.velocity_transformed
    
    def transform_vector(self,source_frame: str,target_frame: str,input_vector: numpy.array):
        """ 
            Transforms a vector from source frame to target frame.

        Args:
            source_frame (str): The frame to transform from 
            target_frame (str): The frame to transform to
            input_array (numpy.array): The vector in source frame as array

        Returns:
            numpy.array: The vector in target frame as array
        """
        source_frame_cartesian_velocity_trans = Vector3Stamped()
        source_frame_cartesian_velocity_rot = Vector3Stamped()
        
        # Get current time stamp
        now = rospy.Time()
 
        # Converse input_vector translation from numpy.array to vector3
        source_frame_cartesian_velocity_trans.header.frame_id = source_frame
        source_frame_cartesian_velocity_trans.header.stamp = now
        source_frame_cartesian_velocity_trans.vector.x = input_vector[0]
        source_frame_cartesian_velocity_trans.vector.y = input_vector[1]
        source_frame_cartesian_velocity_trans.vector.z = input_vector[2]
        
        # Transform input_vector translation from 'wrist_3_link' frame to 'base_link' frame
        target_frame_cartesian_velocity_trans = self.tf_listener.transformVector3(target_frame,source_frame_cartesian_velocity_trans)
        
        # Converse input_vector rotation from numpy.array to vector3
        source_frame_cartesian_velocity_rot.header.frame_id = source_frame
        source_frame_cartesian_velocity_rot.header.stamp = now
        source_frame_cartesian_velocity_rot.vector.x = input_vector[3]
        source_frame_cartesian_velocity_rot.vector.y = input_vector[4]
        source_frame_cartesian_velocity_rot.vector.z = input_vector[5]
        
        # Transform input_vector rotation from 'wrist_3_link' frame to 'base_link' frame
        target_frame_cartesian_velocity_transrot = self.tf_listener.transformVector3(target_frame,source_frame_cartesian_velocity_rot)
        
        # Converse input_vector from vector3 to numpy.array
        output_vector = numpy.array([
            target_frame_cartesian_velocity_trans.vector.x,
            target_frame_cartesian_velocity_trans.vector.y,
            target_frame_cartesian_velocity_trans.vector.z,
            target_frame_cartesian_velocity_transrot.vector.x,
            target_frame_cartesian_velocity_transrot.vector.y,
            target_frame_cartesian_velocity_transrot.vector.z
            ])
        
        return output_vector

    def control_thread(self):
        """ 
            This thread calculates and publishes the target joint velocity using and admittance controller.
        """
        rate = rospy.Rate(self.publish_rate)
        while not rospy.is_shutdown():
            
            # * Calculate velocity from wrench difference and admittance in 'wrist_3_link' frame
            self.admittance_velocity[0] = numpy.sign(self.wrench_ext_filtered.wrench.force.x) * (numpy.abs(self.wrench_ext_filtered.wrench.force.x) * pow((self.P_trans_x * (numpy.abs(self.wrench_ext_filtered.wrench.force.x)/self.publish_rate) + self.D_trans_x),-1))
            
            self.admittance_velocity[1] = numpy.sign(self.wrench_ext_filtered.wrench.force.y) * (numpy.abs(self.wrench_ext_filtered.wrench.force.y) * pow((self.P_trans_y * (numpy.abs(self.wrench_ext_filtered.wrench.force.y)/self.publish_rate) + self.D_trans_y),-1))         
            
            self.admittance_velocity[2] = numpy.sign(self.wrench_ext_filtered.wrench.force.z) * (numpy.abs(self.wrench_ext_filtered.wrench.force.z) * pow((self.P_trans_z * (numpy.abs(self.wrench_ext_filtered.wrench.force.z)/self.publish_rate) + self.D_trans_z),-1))     
            
            self.admittance_velocity[3] = numpy.sign(self.wrench_ext_filtered.wrench.torque.x) * (numpy.abs(self.wrench_ext_filtered.wrench.torque.x) * pow((self.P_rot_x * (numpy.abs(self.wrench_ext_filtered.wrench.torque.x)/self.publish_rate) + self.D_rot_x),-1))    
                                                                                
            self.admittance_velocity[4] = numpy.sign(self.wrench_ext_filtered.wrench.torque.y) * (numpy.abs(self.wrench_ext_filtered.wrench.torque.y) * pow((self.P_rot_y * (numpy.abs(self.wrench_ext_filtered.wrench.torque.y)/self.publish_rate) + self.D_rot_y),-1))
            
            self.admittance_velocity[5] = numpy.sign(self.wrench_ext_filtered.wrench.torque.z) * (numpy.abs(self.wrench_ext_filtered.wrench.torque.z) * pow((self.P_rot_z * (numpy.abs(self.wrench_ext_filtered.wrench.torque.z)/self.publish_rate) + self.D_rot_z),-1))
            
            self.admittance_velocity_transformed = self.transform_velocity(self.admittance_velocity)
            
            # print("self.admittance_velocity_transformed")
            # print(self.admittance_velocity_transformed)
            
            # print("self.base_link_desired_velocity")
            # print(self.base_link_desired_velocity)
            
            # * Add the desired_velocity in 'base_link' frame and admittance velocity in 'base_link' frame
            # self.target_cartesian_velocity[0] = self.base_link_desired_velocity[0] + self.admittance_velocity_transformed[0]
            # self.target_cartesian_velocity[1] = self.base_link_desired_velocity[1] + self.admittance_velocity_transformed[1]
            # self.target_cartesian_velocity[2] = self.base_link_desired_velocity[2] + self.admittance_velocity_transformed[2]
            # self.target_cartesian_velocity[3] = self.base_link_desired_velocity[3] + self.admittance_velocity_transformed[3]
            # self.target_cartesian_velocity[4] = self.base_link_desired_velocity[4] + self.admittance_velocity_transformed[4]
            # self.target_cartesian_velocity[5] = self.base_link_desired_velocity[5] + self.admittance_velocity_transformed[5]
            
            self.target_cartesian_velocity[0] = self.base_link_desired_velocity[0] 
            self.target_cartesian_velocity[1] = self.base_link_desired_velocity[1] 
            self.target_cartesian_velocity[2] = self.base_link_desired_velocity[2] 
            self.target_cartesian_velocity[3] = self.base_link_desired_velocity[3] 
            self.target_cartesian_velocity[4] = self.base_link_desired_velocity[4] 
            self.target_cartesian_velocity[5] = self.base_link_desired_velocity[5] 

            # print("target_cartesian_velocity: befor check for limits")
            # print(self.target_cartesian_velocity)

            # * Check self.target_cartesian_velocity for the min/max velocity limits
            # Calculate the norm of target_cartesian_velocity (trans and rot)
            target_cartesian_trans_velocity_norm = math.sqrt(pow(self.target_cartesian_velocity[0],2) + pow(self.target_cartesian_velocity[1],2) + pow(self.target_cartesian_velocity[2],2))
            
            target_cartesian_rot_velocity_norm = math.sqrt(pow(self.target_cartesian_velocity[3],2) + pow(self.target_cartesian_velocity[4],2) + pow(self.target_cartesian_velocity[5],2))
            

            # print("target_cartesian_trans_velocity_norm")
            # print(target_cartesian_trans_velocity_norm)

            #  Check for cartesian velocity max limit and set to max limit, if max limit is exceeded
            if target_cartesian_trans_velocity_norm > self.cartesian_velocity_trans_max_limit:
                for i in range(3):
                    self.target_cartesian_velocity[i] = (self.target_cartesian_velocity[i]/target_cartesian_trans_velocity_norm) * self.cartesian_velocity_trans_max_limit
                    
            if target_cartesian_rot_velocity_norm > self.cartesian_velocity_rot_max_limit:
                for i in range(3,6):
                    self.target_cartesian_velocity[i] = (self.target_cartesian_velocity[i]/target_cartesian_rot_velocity_norm) * self.cartesian_velocity_rot_max_limit
            
            # Check for cartesian velocity min limit and set to null, if min limit is understeps
            if target_cartesian_trans_velocity_norm < self.cartesian_velocity_trans_min_limit:
                for i in range(3):
                    self.target_cartesian_velocity[i] = 0.0
            
            if target_cartesian_rot_velocity_norm < self.cartesian_velocity_rot_min_limit:
                for i in range(3,6):
                    self.target_cartesian_velocity[i] = 0.0
            
            # print("target_cartesian_velocity: after check for limits")
            # print(self.target_cartesian_velocity)
            
            # * Get the current joint states 
            self.current_joint_states_array = self.group.get_current_joint_values() 
            
            #print("self.current_joint_states_array: ")
            #print(self.current_joint_states_array)
            
            # * Calculate the jacobian-matrix
            self.jacobian = self.group.get_jacobian_matrix(self.current_joint_states_array)
            
            
            # * Calculate the inverse of the jacobian-matrix
            self.inverse_jacobian = numpy.linalg.inv(self.jacobian)
            
#-----------------------------------------------------------------------------------------------------------------------
            # * Singulartiy avoidance: OLMM
            # QIU, Changwu; CAO, Qixin; MIAO, Shouhong. An on-line task modification method for singularity avoidance of robot manipulators. Robotica, 2009, 27. Jg., Nr. 4, S. 539-546.
            
            
           
            
            self.target_cartesian_velocity_old = self.target_cartesian_velocity 
            # Reset the singularity counter
            self.singularity_counter = 0
            # Do a singular value decomposition of the jacobian
            u,s,v = numpy.linalg.svd(self.jacobian,full_matrices=True)
            
            sigma_min = min(s) 
            s_length = len(s) - 1
            
            #* If a singularity is detected
            if sigma_min < 0.05:
                if self.bool_singularity == False:
                    # Set bool singularity to 'True'
                    self.bool_singularity = True
                    rospy.loginfo("Activate OLMM")
                
                # Check if the manipulators movement is a rotation or sigma_min is smaller then singularity_min_threshold
                if (numpy.asarray(self.base_link_desired_velocity[-3:]) != 0.0).any() and self.singularity_min_threshold > sigma_min and self.singularity_stop == False:
                    # if true, set the singularity stop to 'True'
                    self.singularity_stop = True
        
                if self.singularity_stop == False:
                    # Compute singularity avoidance velocity
                    self.singularity_avoidance_velocity = numpy.dot(self.scalar_adjusting_function(sigma_min),numpy.dot(numpy.dot(u[:,s_length],self.target_cartesian_velocity),u[:,s_length]))
                else:
                    self.singularity_avoidance_velocity = [0.0,0.0,0.0,0.0,0.0,0.0]

                        
            # Check sigma min is between 0.05 and 0.08 and a singularity was detected, 
            if 0.05 < sigma_min < 0.08 and self.bool_singularity == True:

                self.singularity_avoidance_velocity = numpy.dot(self.scalar_adjusting_function(sigma_min),numpy.dot(numpy.dot(u[:,s_length],self.target_cartesian_velocity),u[:,s_length]))
                
            # If a singularity was detected but sigma_min is bigger then 0.08
            if sigma_min > 0.08 and self.bool_singularity == True:

                # Reset the bool_singularity and acitivate the bool_reduce_singularity_offset
                self.bool_singularity = False
                self.bool_reduce_singularity_offset = True
                rospy.loginfo("Deactivate OLMM")
                # Reset the singularity velocity world to zero
                self.singularity_avoidance_velocity = [0.0,0.0,0.0,0.0,0.0,0.0]
                
                
            # Transform the singularity avoidance velocity into 'world' frame
            self.singularity_velocity_world = self.transform_vector('base_link','world',self.singularity_avoidance_velocity)
            #
            self.singularity_velocity_msg.singularity_stop = self.singularity_stop
            self.singularity_velocity_msg.singularity_velocity = self.singularity_velocity_world
            # Publish the singularity avoidance velocity to rosmaster
            self.singularity_velocity_pub.publish(self.singularity_velocity_msg)  
                
            
            
            
            # if self.bool_reduce_singularity_offset == True:
                
            #     # World 'frame'
            #     world_EE_pose = self.group.get_current_pose('wrist_3_link')
                
            #     world_EE_quaternion = (world_EE_pose.pose.orientation.x,
            #                             world_EE_pose.pose.orientation.y,
            #                             world_EE_pose.pose.orientation.z,
            #                             world_EE_pose.pose.orientation.w)
        
            #     world_EE_euler = euler_from_quaternion(world_EE_quaternion)
                
            #     world_EE_pose_array = numpy.array([world_EE_pose.pose.position.x,
            #                                         world_EE_pose.pose.position.y,
            #                                         world_EE_pose.pose.position.z,
            #                                         world_EE_euler[0],
            #                                         world_EE_euler[1],
            #                                         world_EE_euler[2]])

            #     base_link_EE_pose_array = self.pose_stamped_transformation('world','base_link',world_EE_pose_array)
                
            #     # In 'base_link' frame
            #     singularity_offset_vector = self.current_EE_pose - base_link_EE_pose_array
                

                
            #     singularity_trans_offset_vector = copy.deepcopy(singularity_offset_vector)
            #     singularity_trans_offset_vector[-3:] = 0.0
                
            #     # print("singularity_trans_offset_vector")
              
            #     # print(numpy.linalg.norm(singularity_trans_offset_vector))
                
            #     singularity_rot_offset_vector = copy.deepcopy(singularity_offset_vector)
            #     singularity_rot_offset_vector[:3] = 0.0
                
            #     for i in range(3):
            #         if abs(singularity_rot_offset_vector[i+3]) > 3.14: 
            #             singularity_rot_offset_vector[i+3] = abs(singularity_rot_offset_vector[i+3]) - 6.28
                        

    
            #     target_trans_cartesian_velocity = copy.deepcopy(self.target_cartesian_velocity)
            #     target_trans_cartesian_velocity[-3:] = 0.0 
                
            #     target_rot_cartesian_velocity = copy.deepcopy(self.target_cartesian_velocity)
            #     target_rot_cartesian_velocity[:3] = 0.0 
                
            #     singularity_trans_offset_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
            #     singularity_rot_offset_velocity = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
            #     # u is in 'base_link' frame
            #     # Translation velocity----------------------------------------------------------------------------------
            #     if numpy.linalg.norm(singularity_trans_offset_vector) > self.singularity_trans_offset_accuracy:
            #             # rospy.loginfo("Reduce Endeffector offset")
                        
                        
            #             # Save the last target cartesian velocity command
            #             if (self.last_target_trans_cartesian_velocity != target_trans_cartesian_velocity).any() and numpy.linalg.norm(target_trans_cartesian_velocity) != 0.0:
            #                 self.last_target_trans_cartesian_velocity = target_trans_cartesian_velocity
                        
            #             # When target cartesian velocity command is not null
            #             if numpy.linalg.norm(target_trans_cartesian_velocity) != 0.0:

            #                 singularity_trans_offset_velocity = (singularity_trans_offset_vector/numpy.linalg.norm(singularity_trans_offset_vector)) * (numpy.linalg.norm(target_trans_cartesian_velocity) + numpy.linalg.norm(singularity_trans_offset_vector)) 
                            
            #                 if numpy.linalg.norm(singularity_trans_offset_velocity) > (numpy.linalg.norm(target_trans_cartesian_velocity) * 1.5 ):
                           
            #                     singularity_trans_offset_velocity = (singularity_trans_offset_vector/numpy.linalg.norm(singularity_trans_offset_vector)) * (numpy.linalg.norm(target_trans_cartesian_velocity) * 1.5)
                            
            #             elif numpy.linalg.norm(self.last_target_trans_cartesian_velocity) != 0.0:
            #                 singularity_trans_offset_velocity = (singularity_trans_offset_vector/numpy.linalg.norm(singularity_trans_offset_vector)) * (numpy.linalg.norm(self.last_target_trans_cartesian_velocity) + numpy.linalg.norm(singularity_trans_offset_vector)) 
                            
            #                 if numpy.linalg.norm(singularity_trans_offset_velocity) > (numpy.linalg.norm(self.last_target_trans_cartesian_velocity) * 1.5 ):
                           
            #                     singularity_trans_offset_velocity = (singularity_trans_offset_vector/numpy.linalg.norm(singularity_trans_offset_vector)) * (numpy.linalg.norm(self.last_target_trans_cartesian_velocity) * 1.5)
                                
            #                 if numpy.linalg.norm(singularity_trans_offset_velocity) < numpy.linalg.norm(self.last_target_trans_cartesian_velocity):
            #                     singularity_trans_offset_velocity = singularity_trans_offset_vector
                                
            #             elif numpy.linalg.norm(self.last_target_trans_cartesian_velocity) == 0.0:
                       
            #                 singularity_trans_offset_velocity = (singularity_trans_offset_vector/numpy.linalg.norm(singularity_trans_offset_vector)) * 0.001
            #     # Translation velocity----------------------------------------------------------------------------------
            #     # Rotation velocity-------------------------------------------------------------------------------------
            #     if numpy.linalg.norm(singularity_rot_offset_vector) > 0.01:
                        
                       
            #             # Save the last target cartesian velocity command
            #             if (self.last_target_rot_cartesian_velocity != target_rot_cartesian_velocity).any() and numpy.linalg.norm(target_rot_cartesian_velocity) != 0.0:
            #                 self.last_target_rot_cartesian_velocity = target_rot_cartesian_velocity
                        
            #             # When target cartesian velocity command is not null
            #             if numpy.linalg.norm(target_rot_cartesian_velocity) != 0.0:

            #                 singularity_rot_offset_velocity = (singularity_rot_offset_vector/numpy.linalg.norm(singularity_rot_offset_vector)) * (numpy.linalg.norm(target_rot_cartesian_velocity) + numpy.linalg.norm(singularity_rot_offset_vector)) 
                            
            #                 if numpy.linalg.norm(singularity_rot_offset_velocity) > (numpy.linalg.norm(target_rot_cartesian_velocity) * 1.5 ):
                           
            #                     singularity_rot_offset_velocity = (singularity_rot_offset_vector/numpy.linalg.norm(singularity_rot_offset_vector)) * (numpy.linalg.norm(target_rot_cartesian_velocity) * 1.5)
                            
            #             elif numpy.linalg.norm(self.last_target_rot_cartesian_velocity) != 0.0:
            #                 singularity_rot_offset_velocity = (singularity_rot_offset_vector/numpy.linalg.norm(singularity_rot_offset_vector)) * (numpy.linalg.norm(self.last_target_rot_cartesian_velocity) + numpy.linalg.norm(singularity_rot_offset_vector)) 
                            
            #                 if numpy.linalg.norm(singularity_rot_offset_velocity) > (numpy.linalg.norm(self.last_target_rot_cartesian_velocity) * 1.5 ):
                           
            #                     singularity_rot_offset_velocity = (singularity_rot_offset_vector/numpy.linalg.norm(singularity_rot_offset_vector)) * (numpy.linalg.norm(self.last_target_rot_cartesian_velocity) * 1.5)
                                
            #                 if numpy.linalg.norm(singularity_rot_offset_velocity) < numpy.linalg.norm(self.last_rot_target_cartesian_velocity):
            #                     singularity_rot_offset_velocity = singularity_rot_offset_vector
                                
            #             elif numpy.linalg.norm(self.last_target_rot_cartesian_velocity) == 0.0:
                                
            #                     singularity_rot_offset_velocity = (singularity_rot_offset_vector/numpy.linalg.norm(singularity_rot_offset_vector)) * 0.005 # 0.5 [°/sec]
                                
            #                     print("singularity_rot_offset_vector")
            #                     print(singularity_rot_offset_vector)
            #                     print(numpy.linalg.norm(singularity_rot_offset_vector))
                                        
                                
                                    
                                
                        
            #             if numpy.linalg.norm(singularity_trans_offset_vector) < self.singularity_trans_offset_accuracy:
            #                 singularity_trans_offset_velocity = copy.deepcopy(self.target_cartesian_velocity)
            #                 singularity_trans_offset_velocity[-3:] = 0.0

            #     # Rotation velocity-------------------------------------------------------------------------------------
              
            #     self.target_cartesian_velocity = singularity_trans_offset_velocity + singularity_rot_offset_velocity
                

            #     if numpy.linalg.norm(singularity_trans_offset_vector) < self.singularity_trans_offset_accuracy and numpy.linalg.norm(singularity_rot_offset_vector) < 0.00174:
                       
            #         self.bool_reduce_singularity_offset = False
            #         print("singularity_trans_offset_vector")
            #         print(numpy.linalg.norm(singularity_trans_offset_vector))
                
                
            #         print("singularity_rot_offset_vector")
            #         print(numpy.linalg.norm(singularity_rot_offset_vector))

            #         rospy.loginfo("Endeffector offset is samller then %f",self.singularity_trans_offset_accuracy)
                    
            # # Publish the calculated singular_velocity, in 'base_link' frame
            # self.singular_velocity_msg.data = self.singular_velocity
            # self.singularity_velocity_pub.publish(self.singular_velocity_msg)
            # self.singular_velocity = [0.0,0.0,0.0,0.0,0.0,0.0]
#-----------------------------------------------------------------------------------------------------------------------
            #* Subract the target cartesian velocity with the singularity avoidance velocity
            if self.singularity_stop == False:
                self.target_cartesian_velocity = self.target_cartesian_velocity - self.singularity_avoidance_velocity
            else:
                self.target_cartesian_velocity = [0.0,0.0,0.0,0.0,0.0,0.0]
                
            # * Calculate the target joint velocity with the inverse jacobian-matrix and the target cartesain velociy
            self.target_joint_velocity.data = self.inverse_jacobian.dot(self.target_cartesian_velocity)
            
            # * Publish the target_joint_velocity
            self.joint_velocity_pub.publish(self.target_joint_velocity)
            
            # * Sleep for publish_rate
            rate.sleep()

    def shutdown(self):
        """ 
            This function is called by rospy.on_shutdown!
        """
        print("Shutdown amittcance controller:")
        print("Shutdown publisher joint velocity!")
        self.joint_velocity_pub.publish(self.shutdown_joint_velocity)
        print("Unregister from joint_velocity_pub!")
        self.joint_velocity_pub.unregister()
        print("Unregister from wrench_ext_sub!")
        self.wrench_ext_sub.unregister()
    
if __name__ == '__main__':
    ur_admittance_controller()
    