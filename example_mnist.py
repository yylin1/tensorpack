#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# File: example_mnist.py
# Author: Yuxin Wu <ppwwyyxx@gmail.com>


# prefer protobuf in user-namespace
import sys
import os
sys.path.insert(0, os.path.expanduser('~/.local/lib/python2.7/site-packages'))

import tensorflow as tf
import numpy as np
from itertools import count


from layers import *
from utils import *
from dataflow.dataset import Mnist
from dataflow import *

IMAGE_SIZE = 28
NUM_CLASS = 10
batch_size = 128
LOG_DIR = 'train_log'

def get_model(inputs):
    """
    Args:
        inputs: a list of input variable,
        e.g.: [input, label] with:
            input: bx28x28
            label: bx1 integer
    Returns:
        (outputs, cost)
        outputs: a list of output variable
        cost: scalar variable
    """
    # use this dropout variable! it will be set to 1 at test time
    keep_prob = tf.placeholder(tf.float32, shape=tuple(), name=DROPOUT_PROB_OP_NAME)

    input, label = inputs

    input = tf.reshape(input, [-1, IMAGE_SIZE, IMAGE_SIZE, 1])
    conv0 = Conv2D('conv0', input, out_channel=32, kernel_shape=5,
                  padding='valid')
    conv0 = tf.nn.relu(conv0)
    pool0 = tf.nn.max_pool(conv0, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1],
                           padding='SAME')
    conv1 = Conv2D('conv1', pool0, out_channel=40, kernel_shape=3,
                  padding='valid')
    conv1 = tf.nn.relu(conv1)
    pool1 = tf.nn.max_pool(conv1, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1],
                           padding='SAME')

    feature = batch_flatten(pool1)

    fc0 = FullyConnected('fc0', feature, 1024)
    fc0 = tf.nn.relu(fc0)
    fc0 = tf.nn.dropout(fc0, keep_prob)

    fc1 = FullyConnected('lr', fc0, out_dim=10)
    prob = tf.nn.softmax(fc1, name='output')

    y = one_hot(label, NUM_CLASS)
    cost = tf.nn.softmax_cross_entropy_with_logits(fc1, y)
    cost = tf.reduce_mean(cost, name='cost')

    # number of correctly classified samples
    correct = tf.equal(
        tf.cast(tf.argmax(prob, 1), tf.int32), label)
    correct = tf.reduce_sum(tf.cast(correct, tf.int32), name='correct')

    return [prob, correct], cost

def main():
    dataset_train = BatchData(Mnist('train'), batch_size)
    dataset_test = BatchData(Mnist('test'), batch_size, remainder=True)
    callbacks = [
        SummaryWriter(LOG_DIR),
        AccuracyValidation(
            dataset_test,
            prefix='test', period=1),
        TrainingAccuracy(),
        PeriodicSaver(LOG_DIR, period=1)
    ]
    optimizer = tf.train.AdamOptimizer(1e-4)
    sess_config = tf.ConfigProto()
    sess_config.device_count['GPU'] = 1

    with tf.Graph().as_default():
        G = tf.get_default_graph()
        image_var = tf.placeholder(tf.float32, shape=(None, IMAGE_SIZE, IMAGE_SIZE), name='input')
        label_var = tf.placeholder(tf.int32, shape=(None,), name='label')
        input_vars = [image_var, label_var]

        for v in input_vars:
            G.add_to_collection(INPUT_VARS_KEY, v)
        output_vars, cost_var = get_model(input_vars)
        for v in output_vars:
            G.add_to_collection(OUTPUT_VARS_KEY, v)

        train_op = optimizer.minimize(cost_var)

        sess = tf.Session(config=sess_config)
        sess.run(tf.initialize_all_variables())

        with sess.as_default():
            for ext in callbacks:
                ext.before_train()

            keep_prob_var = G.get_tensor_by_name(DROPOUT_PROB_VAR_NAME)
            for epoch in count(1):
                for dp in dataset_train.get_data():
                    feed = {keep_prob_var: 0.5}
                    feed.update(dict(zip(input_vars, dp)))

                    results = sess.run(
                        [train_op, cost_var] + output_vars, feed_dict=feed)
                    cost = results[1]
                    outputs = results[2:]
                    assert len(outputs) == len(output_vars)
                    for cb in callbacks:
                        cb.trigger_step(dp, outputs, cost)

                for cb in callbacks:
                    cb.trigger_epoch()
        summary_writer.close()



if __name__ == '__main__':
    main()
