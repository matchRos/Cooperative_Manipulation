#!/usr/bin/env python3

# /***************************************************************************

#
# @package: panda_siimulator_examples
# @metapackage: panda_simulator
# @author: Saif Sidhik <sxs1412@bham.ac.uk>
#

# **************************************************************************/

# /***************************************************************************
# Copyright (c) 2019-2021, Saif Sidhik

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# **************************************************************************/

"""
    Description...

    Impedance controller

    Input:
    * Desired cartesian velocity of the EE: desired_velocity (In 'world' frame)

    Output:
    * Joint effort: self.command_msg.effort (Float64MultiArray)
"""
from tf import transformations
import copy, numpy, quaternion, math
from matplotlib.cbook import flatten
import rospy
import tf
import tf2_ros
from geometry_msgs.msg import Twist, TransformStamped
from std_msgs.msg import Float64MultiArray
from franka_msgs.msg import FrankaState
import moveit_commander
import sys



class franka_impedance_controller():

    def config(self):
        # Stiffness gains
        # self.P_trans_x = 400.
        # self.P_trans_y = 400.
        # self.P_trans_z = 400.
        # self.P_rot_x = 10.
        # self.P_rot_y = 10.
        # self.P_rot_z = 10.
        # # Damping gains
        # self.D_trans_x = 10.
        # self.D_trans_y = 10.
        # self.D_trans_z = 10.
        # self.D_rot_x = 1.
        # self.D_rot_y = 1.
        # self.D_rot_z = 1.
        # # Wrench compliance gains
        # self.wrench_force_x = 0.1
        # self.wrench_force_y = 0.1
        # self.wrench_force_z = 0.1
        # self.wrench_torque_x = 0.1
        # self.wrench_torque_y = 0.1
        # self.wrench_torque_z = 0.1
        # # Wrench filter force treshold (1.0 when robot stands still)
        # self.wrench_filter_force = 1.0
        # # Wrench filter torque treshold (0.14 when robot stands still)
        # self.wrench_filter_torque = 0.14
        # Min and max limits for the cartesian velocity (trans/rot) (unit: [m/s],[rad/s])
        self.cartesian_velocity_trans_min_limit = 0.001
        self.cartesian_velocity_trans_max_limit = 0.1
        self.cartesian_velocity_rot_min_limit = 0.001
        self.cartesian_velocity_rot_max_limit = 0.1
        # Control thread publish rate
        self.publish_rate = 100 # [Hz]
        # Declare librarys for jacobian matrix, cartesian pose and velocity
        # self.JACOBIAN   = None
        # self.CARTESIAN_POSE = None
        # self.CARTESIAN_VEL = None
        # Create joint command message 
        self.command_msg = Float64MultiArray()
        # Initialize position and orientation difference
        # self.delta_pos = numpy.array([0.0,0.0,0.0]).reshape([3,1])
        # self.delta_ori = numpy.array([0.0,0.0,0.0]).reshape([3,1])
        # # Initialize linear and angular velocity difference
        # self.delta_linear = numpy.array([0.0,0.0,0.0]).reshape([3,1])
        # self.delta_angular = numpy.array([0.0,0.0,0.0]).reshape([3,1])
        # Initialize desired translational and rotation velocity
        self.desired_velocity_trans_transformed  = numpy.array([0.0,0.0,0.0])
        self.desired_velocity_rot_transformed  = numpy.array([0.0,0.0,0.0])
        # Initialize external wrench
        # self.wrench_transformed = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0])
        # self.wrench_force_transformed = numpy.array([0.0,0.0,0.0,])
        # self.wrench_torque_transformed = numpy.array([0.0,0.0,0.0,])
        # # Initialize trajectory velocity for object rotation
        self.world_trajectory_velocity = numpy.array([0.0,0.0,0.0])
        # The gripper offset
        self.panda_gripper_offset = 0.10655





    def __init__(self):
        # * Load config parameters
        self.config()

        # * Initialize node
        rospy.init_node("ts_control_sim_only")

         # * Initialize tf TransformBroadcaster
        self.brodacaster = tf2_ros.StaticTransformBroadcaster()
        # * Initialize tf TransformListener
        self.tf_listener = tf.TransformListener()

        # Wait for transformations in tf tree
        rospy.loginfo("Wait for transformation '/panda_link8' to 'world'.")
        self.tf_listener.waitForTransform("/panda_link8","/world", rospy.Time(), rospy.Duration(5.0))
        rospy.loginfo("Wait for transformation '/panda_link0' to '/panda_link8'.")
        self.tf_listener.waitForTransform("/panda_link0","/panda_link8", rospy.Time(), rospy.Duration(5.0))
        rospy.loginfo("Wait for transformation 'world' to '/panda_link0'.")
        self.tf_listener.waitForTransform("world","/panda_link0", rospy.Time(), rospy.Duration(5.0))
        # Initialize the 'padna/panda_gripper' frame in tf tree
        self.set_gripper_offset()
        # Wait for transformations from 'world' to 'panda_gripper' and 'world' to 'ur16e_gripper'
        rospy.loginfo("Wait for transformation 'world' to '/panda_link8'.")
        self.tf_listener.waitForTransform("world","/panda_link8", rospy.Time(), rospy.Duration(10.0))
        # rospy.loginfo("Wait for transformation 'world' to 'ur16e_gripper'.")
        # self.tf_listener.waitForTransform("world","ur16e_gripper", rospy.Time(), rospy.Duration(10.0))
        # ! If not using franka_ros_interface, you have to subscribe to the right topics to obtain the current end-effector state and robot jacobian for computing commands
        # * Initialize move_it
        # You have to launch roslaunch panda_moveit_config move_group.launch
        # moveit_commander.roscpp_initialize(sys.argv)

        # try:
        #     group_name = 'panda_arm'
        #     print("Initialize movit_commander. Group name: ",group_name)
        #     self.group = moveit_commander.MoveGroupCommander(group_name, wait_for_servers=5.0)
        # except Exception as e:
        #     print(e)

        # * Initialize subscriber:
        # self.cartesian_state_sub = rospy.Subscriber(
        #     '/franka_state_controller/franka_states',
        #     FrankaState,
        #     self._get_franka_state,
        #     queue_size=1,
        #     tcp_nodelay=True)

        # Wait for messages to be populated before proceeding
        # rospy.wait_for_message("/franka_state_controller/franka_states",FrankaState,timeout=5.0)

        self.cartesian_msg_sub = rospy.Subscriber(
            '/cooperative_manipulation/cartesian_velocity_command',
            Twist,
            self.cartesian_msg_callback,
            queue_size=1,
            tcp_nodelay=True)

        # self.wrench_msg_sub = rospy.Subscriber(
        #     'franka_state_controller/F_ext',
        #     WrenchStamped,
        #     self.wrench_msg_callback,
        #     queue_size=1,
        #     tcp_nodelay=True)

        # * Initialize publisher:
        # Also create a publisher to publish joint commands
        self.velocity_command_publisher = rospy.Publisher(
                '/franka_impedance_controller/desired_velocity',
                Float64MultiArray,
                tcp_nodelay=True,
                queue_size=1)

        # # * Get the current joint states
        # self.current_joint_states_array = self.group.get_current_joint_values()

        # # * Calculate the jacobian-matrix
        # self.JACOBIAN   = self.group.get_jacobian_matrix(self.current_joint_states_array)


        # # Wait for messages to be populated before proceeding
        # rospy.loginfo("Subscribing to robot state topics...")
        # while (True):
        #     if not (self.JACOBIAN   is None or self.CARTESIAN_POSE is None):
        #         print(self.JACOBIAN  ,self.CARTESIAN_POSE)
        #         break
        # rospy.loginfo("Recieved messages; Launch Franka Impedance Control.")



        # * Initialize on_shutdown clean up
        rospy.on_shutdown(self._on_shutdown)

        # * Get start position and orientation
        # start_pose = copy.deepcopy(self.CARTESIAN_POSE)
        # start_pos, start_ori = start_pose['position'],start_pose['orientation']

        # * Initialize self.goal_pos and self.goal_ori
        # self.goal_pos = numpy.asarray(start_pos.reshape([1,3]))
        # self.goal_ori = start_ori

        # * Initialize P_trans/P_rot and D_trans/D_rot numpy.array
        # self.P_trans = numpy.array([self.P_trans_x,self.P_trans_y,self.P_trans_z]).reshape([3,1])
        # self.P_rot = numpy.array([self.P_rot_x,self.P_rot_y,self.P_rot_z]).reshape([3,1])
        # self.D_trans = numpy.array([self.D_trans_x,self.D_trans_y,self.D_trans_z]).reshape([3,1])
        # self.D_rot = numpy.array([self.D_rot_x,self.D_rot_y,self.D_rot_z]).reshape([3,1])


        # # * Run controller thread
        self.control_thread()

        print("ros spin")
        rospy.spin()

    def control_thread(self):
        """
            Actual control loop. Uses goal pose from the feedback thread
            and current robot states from the subscribed messages to compute
            task-space force, and then the corresponding joint torques.
        """
        # Set rospy.rate
        rate = rospy.Rate(self.publish_rate)
        # Declare movement_trans and movement_ori
        # movement_trans = numpy.array([None])
        # movement_ori = numpy.array([None])
        
        # time_old = rospy.Time.now()
        # time_old = time_old.to_sec() - 0.01

        while not rospy.is_shutdown():
            # Get current position and orientation
            # curr_pose = copy.deepcopy(self.CARTESIAN_POSE)
            # curr_pos, curr_ori = curr_pose['position'],curr_pose['orientation']
            # # Get current linear and angular velocity
            # current_vel_trans = (self.CARTESIAN_VEL['linear']).reshape([3,1])
            # current_vel_rot = (self.CARTESIAN_VEL['angular']).reshape([3,1])

            # print("current_vel_rot ")
            # print(current_vel_rot )


            # * Check self.target_cartesian_trans_velocity and self.target_cartesian_trot_velocity for the min/max velocity limits
            # Calculate the norm of target_cartesian_velocity (trans and rot)
            target_cartesian_trans_velocity_norm = numpy.linalg.norm(self.desired_velocity_trans_transformed)
            target_cartesian_rot_velocity_norm = numpy.linalg.norm(self.desired_velocity_rot_transformed)

            # print("numpy.linalg.norm(self.desired_velocity_trans_transformed)")
            # print(numpy.linalg.norm(self.desired_velocity_trans_transformed))

            # Check whether the trans/rot velocity  limit has been exceeded. If the trans/rot velocity max limit has been exceeded, then normalize the velocity to the length of the velocity upper limit
            if target_cartesian_trans_velocity_norm > self.cartesian_velocity_trans_max_limit:
                for i in range(3):
                    self.desired_velocity_trans_transformed[i] = (self.desired_velocity_trans_transformed[i]/target_cartesian_trans_velocity_norm) * self.cartesian_velocity_trans_max_limit

            if target_cartesian_rot_velocity_norm > self.cartesian_velocity_rot_max_limit:
                for i in range(3):
                    self.desired_velocity_rot_transformed[i] = (self.desired_velocity_rot_transformed[i]/target_cartesian_rot_velocity_norm) * self.cartesian_velocity_rot_max_limit


            # Check whether the velocity limit has been undershot. If the velocity  has fallen below the min velocity limit, then set the velocity  to zero
            if target_cartesian_trans_velocity_norm < self.cartesian_velocity_trans_min_limit:
                for i in range(3):
                    self.desired_velocity_trans_transformed[i] = 0.0

            if target_cartesian_rot_velocity_norm < self.cartesian_velocity_rot_min_limit:
                for i in range(3):
                    self.desired_velocity_rot_transformed[i] = 0.0
                    
            self.command_msg.data = numpy.append(self.desired_velocity_trans_transformed,self.desired_velocity_rot_transformed) 

            print("self.command_msg")
            print(self.command_msg)
            # Transpose the transformation_matrix to hand the impedance controller the values in the correct order
 
            self.velocity_command_publisher.publish(self.command_msg)

            # Calculate the translational and rotation movement
            # movement_trans = numpy.asarray([x / self.publish_rate for x in self.desired_velocity_trans_transformed]).reshape([1,3])
            # movement_ori = self.euler_to_quaternion(numpy.asarray([x / self.publish_rate for x in self.desired_velocity_rot_transformed]))
            
            
            

            # time_now = rospy.Time.now()
            # time_now = time_now.to_sec()
            # time_diff = numpy.round(time_now - time_old,3)
            # time_old = time_now
            
            # if target_cartesian_trans_velocity_norm == 0.0 and target_cartesian_rot_velocity_norm == 0.0:
            #     tau = numpy.array([0.0,0.0,0.0,0.0,0.0,0.0,0.0])
            #     # ! Only for real robot with effort_controllers/JointGroupEffoertController. If you send zero torques to the effort_controllers/JointGroupEffoertController the controller compute the equilibrium pose.
            #     self.command_msg.data = tau.flatten()
            #     self.velocity_command_publisher.publish(self.command_msg)
            #     # ! -------------------------------------------------------------------
                
            #     self.goal_pos = curr_pos
            #     self.goal_ori = curr_ori
                
            # else:
            #     # Calculate the translational and rotation movement
            #     movement_trans = numpy.asarray([x * time_diff for x in self.desired_velocity_trans_transformed]).reshape([1,3])
            #     movement_ori = self.euler_to_quaternion(numpy.asarray([x * time_diff for x in self.desired_velocity_rot_transformed]))

            #     # Add the movement to current pose and orientation
            #     self.goal_pos = (self.goal_pos + movement_trans)
            #     self.goal_ori = self.add_quaternion(self.goal_ori,movement_ori)
            #     # Calculate position and orientation difference
            #     self.delta_pos = (self.goal_pos - curr_pos).reshape([3,1])
            #     self.delta_ori = self.quatdiff_in_euler(curr_ori, self.goal_ori).reshape([3,1])
                
            #     # print("self.wrench_force_transformed")
            #     # print(self.wrench_force_transformed)
            #     # Calculate linear and angular velocity difference
            #     self.delta_linear = numpy.array(self.desired_velocity_trans_transformed).reshape([3,1]) - current_vel_trans
                
            #     #+ numpy.array(self.wrench_force_transformed).reshape([3,1])
            #     self.delta_angular = numpy.array(self.desired_velocity_rot_transformed).reshape([3,1]) - current_vel_rot 
                
            #     #+ numpy.array(self.wrench_torque_transformed).reshape([3,1])
                
            #     # print("self.delta_linear")
            #     # print(self.delta_linear)
                
            #     # Desired task-space force using PD law
            #     F = numpy.vstack([numpy.multiply(self.P_trans,self.delta_pos), numpy.multiply(self.P_rot,self.delta_ori)]) + numpy.vstack([numpy.multiply(self.D_trans,self.delta_linear), numpy.multiply(self.D_rot,self.delta_angular)])

            #     J = copy.deepcopy(self.JACOBIAN)
                
            #     # joint torques to be commanded
            #     tau = numpy.dot(J.T,F)
                
            #     # publish joint commands
            #     self.command_msg.data = tau.flatten()
            #     self.velocity_command_publisher.publish(self.command_msg)
            
            rate.sleep()



    # def _get_franka_state(self,msg):
    #     """
    #         Callback function to get current end-point state.

    #     Args:
    #         msg (franka_core_msgs.msg.EndPointState): Current tip-state state
    #     """
    #     # pose message received is a vectorised column major transformation matrix
    #     cart_pose_trans_mat = numpy.asarray(msg.O_T_EE).reshape(4,4,order='F')

    #     # print("cart_pose_trans_mat")
    #     # print(cart_pose_trans_mat)
        
    #     self.CARTESIAN_POSE = {
    #         'position': cart_pose_trans_mat[:3,3],
    #         'orientation': quaternion.from_rotation_matrix(cart_pose_trans_mat[:3,:3]) }
        
    #     # * Get the current joint states
    #     self.current_joint_states_array = self.group.get_current_joint_values()

    #     # * Calculate the jacobian-matrix
    #     self.JACOBIAN   = self.group.get_jacobian_matrix(self.current_joint_states_array)

    #     O_dP_EE = self.JACOBIAN  .dot(numpy.asarray(msg.dq))


    #     self.CARTESIAN_VEL = {
    #         'linear': numpy.asarray([O_dP_EE[0], O_dP_EE[1], O_dP_EE[2]]),
    #         'angular': numpy.asarray([O_dP_EE[3],O_dP_EE[4], O_dP_EE[5]]) }


    def cartesian_msg_callback(self,desired_velocity):
        """
            Get the cartesian velocity command and transform it from the 'world' frame to the 'panda_link8' (EE-frame)frame and from the 'panda_link8' frame to the 'panda_link0' (0-frame)frame.

            rostopic pub -r 10 /cooperative_manipulation/cartesian_velocity_command geometry_msgs/Twist "linear:
            x: 0.0
            y: 0.0
            z: 0.0
            angular:
            x: 0.0
            y: 0.0
            z: 0.0"

        Args:
            desired_velocity (geometry_msgs.msg.Twist): Desired cartesian velocity
        """
        # Get current time stamp
        now = rospy.Time()
        #------------------------------
        # Calculate the trajectory velocity of the manipulator for a rotation of the object
        # Get self.panda_current_position, self.panda_current_quaternion of the '/panda_link8' frame in the 'world' frame
        panda_tf_time = self.tf_listener.getLatestCommonTime("/world", "/panda_link8")
        panda_current_position, panda_current_quaternion = self.tf_listener.lookupTransform("/world", "/panda_link8", panda_tf_time)


        # Get self.panda_current_position, self.panda_current_quaternion of the '/panda_gripper' frame in the 'world' frame
        panda_tf_time = self.tf_listener.getLatestCommonTime("/world", "/panda_gripper")
        panda_gripper_position, panda_gripper_quaternion = self.tf_listener.lookupTransform("/world", "/panda_gripper", panda_tf_time)

        # Get ur16e_current_position, ur16e_current_quaternion of the 'wrist_3_link' in frame in the 'world' frame
        # ur16e_tf_time = self.tf_listener.getLatestCommonTime("/world", "/wrist_3_link")
        # ur16e_gripper_position, ur16e_gripper_quaternion = self.tf_listener.lookupTransform("/world", "/ur16e_gripper", ur16e_tf_time)

        # print("self.ur16e_current_position, self.ur16e_current_quaternion")
        # print(self.ur16e_current_position, self.ur16e_current_quaternion)
        # print("self.panda_current_position, self.panda_current_quaternion")
        # print(self.panda_position, self.panda_current_quaternion)

        # Object rotation around x axis
        # if desired_velocity.angular.x != 0.0:
        #     panda_current_position_x = numpy.array([
        #         0.0,
        #         panda_current_position[1],
        #         panda_current_position[2]
        #         ])

        #     self.robot_distance_x = numpy.array([
        #         0.0,
        #         ur16e_gripper_position[1] - panda_gripper_position[1],
        #         ur16e_gripper_position[2] - panda_gripper_position[2],
        #     ])

        #     center_x = (numpy.linalg.norm(self.robot_distance_x)/2) * (1/numpy.linalg.norm(self.robot_distance_x)) * self.robot_distance_x + panda_gripper_position
        #     world_desired_rotation_x = numpy.array([desired_velocity.angular.x,0.0,0.0])
        #     world_radius_x = panda_current_position_x - center_x
        #     self.world_trajectory_velocity_x = numpy.cross(world_desired_rotation_x,world_radius_x)
        #     self.world_trajectory_velocity = self.world_trajectory_velocity + self.world_trajectory_velocity_x

        # # Object rotation around y axis
        # if desired_velocity.angular.y != 0.0:
        #     panda_current_position_y = numpy.array([
        #         panda_current_position[0],
        #         0.0,
        #         panda_current_position[2]
        #         ])

        #     self.robot_distance_y = numpy.array([
        #         ur16e_gripper_position[0] - panda_gripper_position[0],
        #         0.0,
        #         ur16e_gripper_position[2] - panda_gripper_position[2],
        #         ])

        #     center_y = (numpy.linalg.norm(self.robot_distance_y)/2) * (1/numpy.linalg.norm(self.robot_distance_y)) * self.robot_distance_y + panda_gripper_position
        #     world_desired_rotation_y = numpy.array([0.0,desired_velocity.angular.y,0.0])
        #     world_radius_y = panda_current_position_y - center_y
        #     self.world_trajectory_velocity_y = numpy.cross(world_desired_rotation_y,world_radius_y)
        #     self.world_trajectory_velocity = self.world_trajectory_velocity + self.world_trajectory_velocity_y



        # # Object rotation around z axis
        # if desired_velocity.angular.z != 0.0:
        #     panda_current_position_z = numpy.array([
        #         panda_current_position[0],
        #         panda_current_position[1],
        #         0.0,
        #         ])

        #     self.robot_distance_z = numpy.array([
        #         ur16e_gripper_position[0] - panda_gripper_position[0],
        #         ur16e_gripper_position[1] - panda_gripper_position[1],
        #         0.0,
        #         ])

        #     center_z = (numpy.linalg.norm(self.robot_distance_z)/2) * (1/numpy.linalg.norm(self.robot_distance_z)) * self.robot_distance_z + panda_gripper_position
        #     world_desired_rotation_z = numpy.array([0.0,0.0,desired_velocity.angular.z])
        #     world_radius_z = panda_current_position_z - center_z
        #     self.world_trajectory_velocity_z = numpy.cross(world_desired_rotation_z,world_radius_z)
        #     self.world_trajectory_velocity = self.world_trajectory_velocity + self.world_trajectory_velocity_z

        #------------------------------

        # world_cartesian_velocity_trans  = Vector3Stamped()
        # world_cartesian_velocity_rot  = Vector3Stamped()
        #  # Converse cartesian_velocity translation to vector3
        # world_cartesian_velocity_trans.header.frame_id = 'world'
        # world_cartesian_velocity_trans.header.stamp = now
        # world_cartesian_velocity_trans.vector.x = desired_velocity.linear.x + self.world_trajectory_velocity[0]
        # world_cartesian_velocity_trans.vector.y = desired_velocity.linear.y + self.world_trajectory_velocity[1]
        # world_cartesian_velocity_trans.vector.z = desired_velocity.linear.z + self.world_trajectory_velocity[2]

        # Transform cartesian_velocity translation from 'world' frame to 'panda_link0' frame and from 'panda_link0' frame to 'panda_link8
        # base_cartesian_velocity_trans = self.tf_listener.transformVector3('panda_link0',world_cartesian_velocity_trans)

        # # Converse cartesian_velocity rotation to vector3
        # world_cartesian_velocity_rot.header.frame_id = 'world'
        # world_cartesian_velocity_rot.header.stamp = now
        # world_cartesian_velocity_rot.vector.x = desired_velocity.angular.x
        # world_cartesian_velocity_rot.vector.y = desired_velocity.angular.y
        # world_cartesian_velocity_rot.vector.z = desired_velocity.angular.z

        # print("world_cartesian_velocity_rot")
        # print(world_cartesian_velocity_rot)

        # Transform cartesian_velocity rotation from 'world' frame to 'panda_link0' frame and from 'panda_link0' frame to 'panda_link8'
        # base_cartesian_velocity_rot = self.tf_listener.transformVector3('panda_link0',world_cartesian_velocity_rot)

        # print("base_cartesian_velocity_rot")
        # print(base_cartesian_velocity_rot)

        # Converse cartesian_velocity from vector3 to numpy.array
        self.desired_velocity_trans_transformed = [
            desired_velocity.linear.x,
            desired_velocity.linear.y,
            desired_velocity.linear.z
            ]

        self.desired_velocity_rot_transformed = [
            desired_velocity.angular.x,
            desired_velocity.angular.y,
            desired_velocity.angular.z,
            ]


        # Set the trajectory velocity for an object rotation to zero
        # self.world_trajectory_velocity = [0.0,0.0,0.0]


    # def wrench_msg_callback(self,wrench_ext):
    #     """
    #         Get external wrench in panda_K.
    #     """
    #     print("wrench_ext")
    #     print(wrench_ext)

    #     # Get current time stamp
    #     now = rospy.Time()

    #     panda_K_wrench_force  = Vector3Stamped()
    #     panda_K_wrench_torque  = Vector3Stamped()
    #     # Converse cartesian_velocity translation to vector3
    #     panda_K_wrench_force.header.frame_id = 'panda_K'
    #     panda_K_wrench_force.header.stamp = now
    #     panda_K_wrench_force.vector.x = wrench_ext.wrench.force.x
    #     panda_K_wrench_force.vector.y = wrench_ext.wrench.force.y
    #     panda_K_wrench_force.vector.z = wrench_ext.wrench.force.z

    #     # Transform cartesian_velocity translation from 'panda_K' frame to 'panda_link8'
    #     base_wrench_force = self.tf_listener.transformVector3('panda_link0',panda_K_wrench_force)

    #     # Converse cartesian_velocity rotation to vector3
    #     panda_K_wrench_torque.header.frame_id = 'panda_K'
    #     panda_K_wrench_torque.header.stamp = now
    #     panda_K_wrench_torque.vector.x = wrench_ext.wrench.torque.x
    #     panda_K_wrench_torque.vector.y = wrench_ext.wrench.torque.y
    #     panda_K_wrench_torque.vector.z = wrench_ext.wrench.torque.z

    #     # Transform cartesian_velocity rotation from 'panda_K' frame to 'panda_link8'
    #     base_wrench_torque = self.tf_listener.transformVector3('panda_link0',panda_K_wrench_torque)

    #     # * Band-passfilter
    #     if numpy.abs(base_wrench_force.vector.x) < self.wrench_filter_force:
    #         base_wrench_force.vector.x = 0.0
    #     else:
    #         base_wrench_force.vector.x = base_wrench_force.vector.x - numpy.sign(base_wrench_force.vector.x) * self.wrench_filter_force

    #     if(numpy.abs(base_wrench_force.vector.y) < self.wrench_filter_force):
    #         base_wrench_force.vector.y = 0.0
    #     else:
    #         base_wrench_force.vector.y = base_wrench_force.vector.y - numpy.sign(base_wrench_force.vector.y) * self.wrench_filter_force

    #     if(numpy.abs(base_wrench_force.vector.z) < self.wrench_filter_force):
    #         base_wrench_force.vector.z = 0.0
    #     else:
    #        base_wrench_force.vector.z = base_wrench_force.vector.z - numpy.sign(base_wrench_force.vector.z) * self.wrench_filter_force

    #     if(numpy.abs(base_wrench_torque.vector.x) < self.wrench_filter_torque):
    #         base_wrench_torque.vector.x = 0.0
    #     else:
    #         base_wrench_torque.vector.x = base_wrench_torque.vector.x - numpy.sign(base_wrench_torque.vector.x) * self.wrench_filter_torque
    #     if(numpy.abs(base_wrench_torque.vector.y) < self.wrench_filter_torque):
    #         base_wrench_torque.vector.y = 0.0
    #     else:
    #         base_wrench_torque.vector.y = base_wrench_torque.vector.y - numpy.sign(base_wrench_torque.vector.y) * self.wrench_filter_torque
    #     if(numpy.abs(base_wrench_torque.vector.z) < self.wrench_filter_torque):
    #         base_wrench_torque.vector.z = 0.0
    #     else:
    #         base_wrench_torque.vector.z = base_wrench_torque.vector.z - numpy.sign(base_wrench_torque.vector.z) * self.wrench_filter_torque
            
            
    #     print("base_wrench_force.")
    #     print(base_wrench_force)
    #     # Converse cartesian_velocity from vector3 to numpy.array and multipy the compliance gains
    #     self.wrench_force_transformed = [
    #         base_wrench_force.vector.x * self.wrench_force_x,
    #         base_wrench_force.vector.y * self.wrench_force_y,
    #         base_wrench_force.vector.z * self.wrench_force_z,
    #         ]

    #     self.wrench_torque_transformed = [
    #         base_wrench_torque.vector.x * self.wrench_torque_x,
    #         base_wrench_torque.vector.y * self.wrench_torque_y,
    #         base_wrench_torque.vector.z * self.wrench_torque_z,
    #         ]
        
    #     print("self.wrench_force_transformed")
    #     print(self.wrench_force_transformed)


    def set_gripper_offset(self):
        """
            Set the gripper offset from 'panda_link8' frame.
        """
        static_gripper_offset = TransformStamped()
        static_gripper_offset.header.stamp = rospy.Time.now()
        static_gripper_offset.header.frame_id = "/panda_link8"
        static_gripper_offset.child_frame_id = "panda_gripper"
        static_gripper_offset.transform.translation.x = 0.0
        static_gripper_offset.transform.translation.y = 0.0
        static_gripper_offset.transform.translation.z = self.panda_gripper_offset
        static_gripper_offset.transform.rotation.x = 0.0
        static_gripper_offset.transform.rotation.y = 0.0
        static_gripper_offset.transform.rotation.z = -0.924
        static_gripper_offset.transform.rotation.w = 0.383

        self.brodacaster.sendTransform(static_gripper_offset)

    # def euler_to_quaternion(self,euler_array: numpy.array):
    #     """
    #         Convert Euler angles to a quaternion.

    #         Inuput
    #             :param alpha: Rotation around x-axis) angle in radians.
    #             :param beta: The beta (rotation around y-axis) angle in radians.
    #             :param gamma: The gamma (rotation around z-axis) angle in radians.

    #         Output
    #             :return quaternion_from_euler: The orientation in quaternion
    #     """
    #     alpha, beta, gamma = euler_array

    #     q_x = numpy.sin(alpha/2) * numpy.cos(beta/2) * numpy.cos(gamma/2) - numpy.cos(alpha/2) * numpy.sin(beta/2) * numpy.sin(gamma/2)
    #     q_y = numpy.cos(alpha/2) * numpy.sin(beta/2) * numpy.cos(gamma/2) + numpy.sin(alpha/2) * numpy.cos(beta/2) * numpy.sin(gamma/2)
    #     q_z = numpy.cos(alpha/2) * numpy.cos(beta/2) * numpy.sin(gamma/2) - numpy.sin(alpha/2) * numpy.sin(beta/2) * numpy.cos(gamma/2)
    #     q_w = numpy.cos(alpha/2) * numpy.cos(beta/2) * numpy.cos(gamma/2) + numpy.sin(alpha/2) * numpy.sin(beta/2) * numpy.sin(gamma/2)


    #     quaternion_from_euler = numpy.quaternion(q_w,q_x,q_y,q_z)


    #     return quaternion_from_euler
    
    
    # # Calculates Rotation Matrix given euler angles.
    # def euler_to_matrix(self,euler_array: numpy.array):
        
    #     if(numpy.linalg.norm(euler_array) != 0.0):
    #         matrix_from_rotation = transformations.euler_matrix(euler_array[0],euler_array[1],euler_array[2])
    #     else:
    #         matrix_from_rotation = numpy.array([[0.0,0.0,0.0,0.0],
    #                                 [0.0,0.0,0.0,0.0],
    #                                 [0.0,0.0,0.0,0.0],
    #                                 [0.0,0.0,0.0,0.0]])
    #     return matrix_from_rotation

    


    # def quatdiff_in_euler(self,quat_curr: numpy.quaternion, quat_des: numpy.quaternion):
    #     """
    #         Compute difference between quaternions and return
    #         Euler angles as difference.

    #     Args:
    #         quat_curr (numpy.quaternion): Current orientation
    #         quat_des (numpy.quaternion): Desired orientation

    #     Returns:
    #         numpy.array: Difference between quaternions
    #     """
    #     curr_mat = quaternion.as_rotation_matrix(quat_curr)
    #     des_mat = quaternion.as_rotation_matrix(quat_des)
    #     rel_mat = des_mat.T.dot(curr_mat)
    #     rel_quat = quaternion.from_rotation_matrix(rel_mat)
    #     vec = quaternion.as_float_array(rel_quat)[1:]
    #     if rel_quat.w < 0.0:
    #         vec = -vec

    #     return -des_mat.dot(vec)

    # def add_quaternion(self,quat_0: numpy.quaternion,quat_1: numpy.quaternion):
    #     """
    #         Add two quaternions and return the sum.

    #     Args:
    #         quat_0 (numpy.quaternion): First quaternion
    #         quat_1 (numpy.quaternion): Second quaternion

    #     Returns:
    #         numpy.quaternion: Sum of both quaternions
    #     """
    #     # Extract the values from Q0
    #     w_0 = quat_0.w
    #     x_0 = quat_0.x
    #     y_0 = quat_0.y
    #     z_0 = quat_0.z
    #     # Extract the values from Q1
    #     w_1 = quat_1.w
    #     x_1 = quat_1.x
    #     y_1 = quat_1.y
    #     z_1 = quat_1.z
    #     # Compute the product of the two quaternions, term by term
    #     sum_w = w_0 * w_1 - x_0 * x_1 - y_0 * y_1 - z_0 * z_1
    #     sum_x = w_0 * x_1 + x_0 * w_1 + y_0 * z_1 - z_0 * y_1
    #     sum_y = w_0 * y_1 - x_0 * z_1 + y_0 * w_1 + z_0 * x_1
    #     sum_z = w_0 * z_1 + x_0 * y_1 - y_0 * x_1 + z_0 * w_1

    #     sum_quat = numpy.quaternion(sum_w ,sum_x,sum_y,sum_z)

    #     return sum_quat

    def _on_shutdown(self):
        """
            Shutdown publisher and subscriber when rosnode dies.
        """
        print("Shutdown impedance controller:")
        print("Shutdown publisher joint velocity!")
        self.velocity_command_publisher.publish(self.velocity_command_publisher)
        print("Unregister from cartesian_state_sub!")
        self.cartesian_state_sub.unregister()


if __name__ == "__main__":
    franka_impedance_controller()