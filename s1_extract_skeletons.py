import sys
import os
sys.path.append('pose2d')

import cv2
import numpy as np
from pose import Pose
from utils.lib_tracker import Tracker
from utils.lib_skeletons_io import ReadValidImagesAndActionTypesByTxt
import utils.lib_commons as lib_commons
import myutils

def remove_persons_with_few_joints(all_keypoints):
    """ Remove bad skeletons before sending to the tracker"""
    good_keypoints = []
    for keypoints in all_keypoints:
        no_head_keypoints = keypoints[5:, 1:]
        num_valid_joints = sum(no_head_keypoints!=0)[0] # number of valid joints (withoud head)
        num_leg_joints = sum(no_head_keypoints[-7:-1]!=0)[0] # number of joints for legs

        if num_valid_joints >= 5 and num_leg_joints >= 0:
            good_keypoints.append(keypoints)
    return np.array(good_keypoints)

def main():

    # setting
    cfg_all = lib_commons.read_yaml('config/config.yaml')
    cfg = cfg_all['s1_extract_skeleton.py']

    # input images cfg
    cfg_img_input = cfg['input']
    img_filename_fmt = cfg_img_input['img_filename_format']

    # Output
    skl_filename_fmt = cfg_all['skeleton_filename_format']
    dst_imgs_info_txt = cfg['output']['images_info_txt']
    dst_skeletons_folder = cfg['output']['detected_skeletons_folder']
    dst_imgs_folder = cfg['output']['viz_images_folder']

    # initiate pose estimator
    cfg_model = cfg['trtpose']
    pose = Pose(cmap_threshold=0.1, link_threshold=0.1, **cfg_model)
    multiperson_tracker = Tracker()

    # load images
    img_loader = ReadValidImagesAndActionTypesByTxt(**cfg_img_input)
    # -- Init output path
    start_image = 0
    img_loader.save_images_info(filepath=dst_imgs_info_txt)
    if os.path.exists(dst_skeletons_folder):
        start_image = len(os.listdir(dst_skeletons_folder))
    os.makedirs(os.path.dirname(dst_skeletons_folder), exist_ok=True)
    os.makedirs(os.path.dirname(dst_imgs_folder), exist_ok=True)

    # -- Read images and process
    total_images = img_loader.num_images

    for i in range(start_image, total_images):
        # -- read image
        img_bgr, lbl, img_info = img_loader.read_image()
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        img_disp = img_bgr.copy()

        # -- detect and draw
        all_keypoints = pose.predict(img_rgb)
        all_keypoints = remove_persons_with_few_joints(all_keypoints)
        pose.draw2D(img_disp, all_keypoints, draw_numbers=True)

        # -- Get skeleton data and save to file
        skeletons, scale_h = pose.keypoints_to_skels_list(all_keypoints)
        # skeletons = remove_skeletons_with_few_joints(skeletons)
        print(f'{i}/{total_images} --> Total_persons : {len(skeletons)}, Total_joints : {sum(np.array(skeletons[0])>0)//2 if skeletons else 0}')
        dict_id2skeleton = multiperson_tracker.track(skeletons)  # dict: (int human id) -> (np.array() skeleton)
        skels_to_save = [img_info + skeleton.tolist() for skeleton in dict_id2skeleton.values()]
        # -- Save result
        # Save skeleton data for training
        filename = skl_filename_fmt.format(i)
        lib_commons.save_listlist(dst_skeletons_folder + filename, skels_to_save)
        # Save the visualized image for debug
        filename = img_filename_fmt.format(i)
        cv2.imwrite(dst_imgs_folder + filename, img_disp)

        cv2.imshow('show', img_disp)
        key = cv2.waitKey(1)
        if key==27:
            break
    print("Program ends")
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
