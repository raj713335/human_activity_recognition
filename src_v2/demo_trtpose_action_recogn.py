# -*- coding: utf-8 -*-
import sys
import os
import time
import cv2
import argparse
import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)

from utils_v2.parser import YamlParser
from utils_v2 import utils, vis
from pose_estimation import TrtPose
from tracking import DeepSort
from classifier import MultiPersonClassifier
import myutils

def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config_deepsort", type=str,
                        default="../configs/deepsort.yaml")
    ap.add_argument('--config_trtpose', type=str,
                        default='../configs/trtpose.yaml')
    ap.add_argument('--config_classifier', type=str,
                        default='../configs/classifier.yaml')
    ap.add_argument('--src', help='input file for pose estimation, video or webcam',
                    default='/home/zmh/hdd/Test_Videos/Tracking/fun_theory_1.mp4')

    ap.add_argument('--tracking', action='store_true', help='use tracking',
                    default=True)
    ap.add_argument('--pair_iou_thresh', type=float,
                    help='iou threshold to match with tracking bbox and skeleton bbox',
                    default=0.5)
    ap.add_argument('--draw_kp_numbers', action='store_true',
                    help='draw keypoints numbers info of each person',
                    default=True)
    ap.add_argument('--save_path', type=str, help='output folder',
                    default='../output')
# =============================================================================
#     ap.add_argument('--add_feature_template', action='store_true',
#                     help='whether add or not feature template in top right corner',
#                     default=False)
# =============================================================================
    return ap.parse_args()


def main():
    pass

if __name__ == '__main__':
    main()
    # configs
    args = get_args()
    cfg = YamlParser()
    cfg.merge_from_file(args.config_deepsort)
    cfg.merge_from_file(args.config_trtpose)
    cfg.merge_from_file(args.config_classifier)

    # initiate video/webcam
    cap = cv2.VideoCapture(args.src)
    assert cap.isOpened(),  f"Can't open video : {args.src}"
    filename = os.path.basename(args.src)

    # initiate trtpose, deepsort and action classifier
    trtpose = TrtPose(**cfg.TRTPOSE)
    deepsort = DeepSort(**cfg.DEEPSORT)
    classifier = MultiPersonClassifier(**cfg.CLASSIFIER)

    frame_cnt = 0
    cv2.namedWindow(filename, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(filename, 640, 480)
    t0 = time.time()
    # loop on captured frames
    while True:
        ret, img_bgr = cap.read()
        if not ret: break
        img_disp = img_bgr.copy()
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # predict keypoints
        trtpose_keypoints = trtpose.predict(img_rgb)
        trtpose_keypoints = trtpose.remove_persons_with_few_joints(trtpose_keypoints,
                                                                   min_total_joints=5,
                                                                   min_leg_joints=2,
                                                                   include_head=True)
        openpose_keypoints = utils.trtpose_to_openpose(trtpose_keypoints)
        skeletons, _ = trtpose.keypoints_to_skeletons_list(openpose_keypoints)

        bboxes = utils.get_skeletons_bboxes(openpose_keypoints, img_bgr)
        if bboxes:
            xywhs = torch.Tensor(bboxes)
            # pass skeleton bboxes to deepsort
            tracks = deepsort.update(xywhs, img_rgb, pair_iou_thresh= args.pair_iou_thresh)
            if tracks:
                actions = classifier.classify(tracks)

        frame_cnt += 1
        if frame_cnt > 30: break
        # skeletons, _ = trtpose.keypoints_to_skeletons_list(all_keypoints)


    cv2.destroyAllWindows()
    cap.release()
