#!/usr/bin/env python3

# /***************************************************************************

# **************************************************************************/


import rospy    
import numpy as np
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64MultiArray
import moveit_commander
import sys



class ur16e_singularity_test():
    
    def config(self):
        # Set the radius and the trajectory velocity of the circular movement
        self.set_trajectory_velocity = 0.1
        # From Start position and singularity entrance threshold = 0.05, radius = 0.156 is the smallest without singularity avoidance
        # radius 0.165 is the biggest without singularity stop
        self.radius = 0.17
        # ! Do not change under here------------------------------------------------------------------------------------
        self.trajectory_velocity_limit = 0.11 # [rad/s]
        self.alpha = 0.0 # [rad]
        self.publish_rate = 100 # [HZ] 
        self.angular_velocity_vector = np.array([0.0,0.0,0.0])
        self.trajectory_msg = Float64MultiArray()
        self.pub_trajectory = np.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.singularity_velocity = np.array([0.0,0.0,0.0,0.0,0.0,0.0])
        self.singular_velocity_msg = Float64MultiArray()
        
        
    def __init__(self):
        
        self.config()
        
        if self.set_trajectory_velocity < self.trajectory_velocity_limit:
            self.angular_velocity_vector[2]= self.set_trajectory_velocity/self.radius
        else:
            print("self.set_trajectory_velocity is bigger than self.trajectory_velocity_limit!")
            
        self.joint_velocity_msg = Twist()
        
        # * Initialize move_it
        moveit_commander.roscpp_initialize(sys.argv)
            
        # * Initialize node
        rospy.init_node('ur16e_singularity_test', anonymous=True)
        
        #* Publish velocity command 
        self.pub_cartesian_velocity_command = rospy.Publisher("/cooperative_manipulation/cartesian_velocity_command", Twist, queue_size=100)
        
        self.pub_world_trajectory = rospy.Publisher("/cooperative_manipulation/world_trajectory", Float64MultiArray, queue_size=1)
        
        rate = rospy.Rate(self.publish_rate)

        self.now_old = rospy.get_rostime().to_sec()

        rospy.loginfo("Start ciruclar movement ...")
        rospy.loginfo("Set radius: %f [m]",self.radius)
        while not rospy.is_shutdown():
            
            if round(self.alpha,2) >= 6.28:
                self.joint_velocity_msg.linear.x = 0.0
                self.joint_velocity_msg.linear.y = 0.0
                self.joint_velocity_msg.linear.z = 0.0
                self.joint_velocity_msg.angular.x = 0.0
                self.joint_velocity_msg.angular.y = 0.0
                self.joint_velocity_msg.angular.z = 0.0
                
                #* Publish the target_joint_velocity
                self.pub_cartesian_velocity_command.publish(self.joint_velocity_msg)
                rospy.loginfo("Stop ciruclar movement!")
                break
            else:
                
                self.circular_movement()
            
                self.now = rospy.get_rostime().to_sec()
                
                self.alpha = self.alpha + (self.angular_velocity_vector[2]/self.publish_rate)
                
                self.now_old = self.now
            
            rate.sleep()
            
    def circular_movement(self):
        """ Compute the cartesian trajectory velocity from the radius_vector and angular_velocity_vector.
            cartesian_velocity = self.angular_velocity_vector x radius_vector
            (v = omega x raius)
        """
        radius_vector = np.array([
            -np.cos(self.alpha) * self.radius,
            -np.sin(self.alpha) * self.radius,
            0.0
        ])
        cartesian_velocity = np.asarray(np.cross(self.angular_velocity_vector,radius_vector))
        self.joint_velocity_msg.linear.x = cartesian_velocity[0]
        self.joint_velocity_msg.linear.y = cartesian_velocity[1]
        self.joint_velocity_msg.linear.z = cartesian_velocity[2]
        self.joint_velocity_msg.angular.x = 0.0
        self.joint_velocity_msg.angular.y = 0.0
        self.joint_velocity_msg.angular.z = 0.0
        
        joint_velocity_array = np.array([self.joint_velocity_msg.linear.x,
                                        self.joint_velocity_msg.linear.y,
                                        self.joint_velocity_msg.linear.z,
                                        self.joint_velocity_msg.angular.x,
                                        self.joint_velocity_msg.angular.y,
                                        self.joint_velocity_msg.angular.z])
        
        #* Publish the target_joint_velocity
        self.pub_cartesian_velocity_command.publish(self.joint_velocity_msg)
        
        
if __name__ == '__main__':
    ur16e_singularity_test()