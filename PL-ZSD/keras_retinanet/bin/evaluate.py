#!/usr/bin/env python

"""
Copyright 2017-2018 Fizyr (https://fizyr.com)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import os
import sys

import keras
import tensorflow as tf

# Allow relative imports when being executed as script.
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    import keras_retinanet.bin

    __package__ = "keras_retinanet.bin"

# Change these to absolute imports if you copy this script outside the keras_retinanet package.
from ..preprocessing.pascal_voc import PascalVocGenerator
from ..preprocessing.csv_generator import CSVGenerator
from ..utils.keras_version import check_keras_version
from ..utils.eval import evaluate
import keras_resnet.models
from keras_retinanet.models import retinanet_vocab_w2v as retinanet
from ..models.resnet import custom_objects
seenclass = 80
#unseenclass = 

def get_session():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)


def create_generator(args):
    if args.dataset_type == 'coco':
        # import here to prevent unnecessary dependency on cocoapi
        from ..preprocessing.coco import CocoGenerator

        validation_generator = CocoGenerator(
            args.coco_path,
            'val2017'
        )
    elif args.dataset_type == 'pascal':
        validation_generator = PascalVocGenerator(
            args.pascal_path,
            'test',
        )
    elif args.dataset_type == 'csv':
        validation_generator = CSVGenerator(
            args.annotations,
            args.classes,
            image_min_side=args.image_min_side,
            image_max_side=args.image_max_side,
        )
    else:
        raise ValueError('Invalid data type received: {}'.format(args.dataset_type))

    return validation_generator


def parse_args(args):
    parser = argparse.ArgumentParser(description='Evaluation script for a RetinaNet network.')
    subparsers = parser.add_subparsers(help='Arguments for specific dataset types.', dest='dataset_type')
    subparsers.required = True

    coco_parser = subparsers.add_parser('coco')
    coco_parser.add_argument('coco_path', help='Path to dataset directory (ie. /tmp/COCO).')

    pascal_parser = subparsers.add_parser('pascal')
    pascal_parser.add_argument('pascal_path', help='Path to dataset directory (ie. /tmp/VOCdevkit).')

    csv_parser = subparsers.add_parser('csv')
    csv_parser.add_argument('annotations', help='Path to CSV file containing annotations for evaluation.')
    csv_parser.add_argument('classes', help='Path to a CSV file containing class label mapping.')

    parser.add_argument('model', help='Path to RetinaNet model.')
    parser.add_argument('--gpu', help='Id of the GPU to use (as reported by nvidia-smi).')
    parser.add_argument('--score-threshold', help='Threshold on score to filter detections with (defaults to 0.05).',
                        default=0.05, type=float)
    parser.add_argument('--iou-threshold', help='IoU Threshold to count for a positive detection (defaults to 0.5).',
                        default=0.5, type=float)
    parser.add_argument('--max-detections', help='Max Detections per image (defaults to 100).', default=100, type=int)
    parser.add_argument('--wordvector', help='Word vectors', default='word_w2v', type=str)
    parser.add_argument('--top', help='Top seen word vectors', default=5, type=int)
    parser.add_argument('--save-path', help='Path for saving images with detections.')
    
    parser.add_argument('--image-min-side',   help='Rescale the image so the smallest side is min_side.', type=int, default=300)
    parser.add_argument('--image-max-side',   help='Rescale the image if the largest side is larger than max_side.', type=int, default=480)

    return parser.parse_args(args)


def main(args=None):
    # parse arguments
    if args is None:
        args = sys.argv[1:]
    args = parse_args(args)

    # make sure keras is the minimum required version
    check_keras_version()

    # optionally choose specific GPU
    if args.gpu:
        os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    keras.backend.tensorflow_backend.set_session(get_session())

    # make save path if it doesn't exist
    if args.save_path is not None and not os.path.exists(args.save_path):
        os.makedirs(args.save_path)

    # create the generator
    generator = create_generator(args)

    # load the model
    print('Loading model, this may take a second...')
    # model = keras.models.load_model(args.model, custom_objects=custom_objects)

    # shafin
    inputs = keras.layers.Input(shape=(None, None, 3))
    resnet = keras_resnet.models.ResNet50(inputs, include_top=False, freeze_bn=True)
    ################################################################################
    model = retinanet.retinanet_bbox(inputs=inputs, num_classes=seenclass, backbone=resnet)
    
    model.load_weights(args.model)

    # print model summary
    print(model.summary())

    # start evaluation
    average_precisions, average_recalls = evaluate(
        generator,
        model,
        iou_threshold=args.iou_threshold,
        score_threshold=args.score_threshold,
        max_detections=args.max_detections,
        top=args.top,
        wordvector=args.wordvector,
        save_path=args.save_path
    )

    # print evaluation
    for label, average_precision in average_precisions.items():
        print(generator.label_to_name(label), '{:.4f}'.format(average_precision))
    '''
    seenMAP = sum(average_precisions.values()[:seenclass]) / seenclass
    #unseenMAP = sum(average_precisions.values()[65:]) / 15
    #HMMAP = (2 * seenMAP * unseenMAP) / (seenMAP + unseenMAP)
    seenRE = sum(average_recalls.values()[:65]) / 65
    #unseenRE = sum(average_recalls.values()[65:]) / 15
    #HMRE = (2 * seenRE * unseenRE) / (seenRE + unseenRE)

    print('Seen mAP: {:.4f} Unseen mAP: {:.4f} HM mAP: {:.4f}'.format(seenMAP,unseenMAP, HMMAP))
    print('Seen Rec: {:.4f} Unseen Rec: {:.4f} HM Rec: {:.4f}'.format(seenRE, unseenRE, HMRE))
    '''
    seenMAP = sum(average_precisions.values()[:seenclass]) / seenclass
    seenRE = sum(average_recalls.values()[:seenclass]) / seenclass
    print('Seen mAP: {:.4f} '.format(seenMAP))
    print('Seen Rec: {:.4f} '.format(seenRE))


if __name__ == '__main__':
    main()
