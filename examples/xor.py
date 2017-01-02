#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hello Gandlf!

This example trains the GAN to approximate four normal distributions centered
around (-1, -1), (-1, 1), (1, -1) and (1, 1). It can be trained as a vanilla
GAN or as an Auxiliary Classifier GAN, where it learns to classify the
which distribution it is part of.

The model doesn't work super well as a vanilla GAN (it is hard to get the
generator to equally distribute among the four distributions) but it is a
good proof-of-concept that can be run quickly on a single CPU. Adding the
supervised part explicitly tells the GAN which distribution a point should
come from, which makes it work much better.

On the Cartesian plane, the classes are:

               |
             2 | 3
               |
            --- ---
               |
             1 | 0
               |

To show all command line options:

    ./examples/xor.py --help

The model runs in unsupervised mode by default. To run as an ACGAN:

    ./examples/xor.py --supervised
"""

from __future__ import print_function

import argparse
import keras

import gandlf
import numpy as np

# For repeatability.
np.random.seed(1667)


def get_training_data(num_samples):
    """Generates some training data."""

    # As (x, y) Cartesian coordinates.
    x = np.random.randint(0, 2, size=(num_samples, 2))

    y = x[:, 0] + 2 * x[:, 1]  # 2-digit binary to integer.
    y = np.cast['int32'](y)

    x = np.cast['float32'](x) * 1.6 - 0.8  # Scales to [-1, 1].
    x += np.random.uniform(-0.2, 0.2, size=x.shape)

    y_ohe = np.cast['float32'](np.eye(4)[y])
    y = np.cast['float32'](np.expand_dims(y, -1))

    return x, y, y_ohe


def build_generator(latent_size):
    """Builds a simple two-layer generator network."""

    latent_layer = keras.layers.Input((latent_size,))
    class_input = keras.layers.Input((1,))

    embeddings = keras.layers.Embedding(4, latent_size, 'glorot_normal')
    flat_embedded = keras.layers.Flatten()(embeddings(class_input))

    input_layer = keras.layers.merge([latent_layer, flat_embedded], mode='mul')
    hidden_layer = keras.layers.Dense(64)(input_layer)
    hidden_layer = keras.layers.LeakyReLU()(hidden_layer)
    output_layer = keras.layers.Dense(2)(hidden_layer)
    output_layer = keras.layers.Activation('tanh')(output_layer)

    return keras.models.Model([latent_layer, class_input], [output_layer])


def build_discriminator():
    """Builds a simple two-layer discriminator network."""

    input_layer = keras.layers.Input((2,))

    hidden_layer = keras.layers.Dense(64)(input_layer)
    hidden_layer = keras.layers.LeakyReLU()(hidden_layer)

    real_fake = keras.layers.Dense(1)(hidden_layer)
    real_fake = keras.layers.Activation('sigmoid', name='src')(real_fake)

    class_pred = keras.layers.Dense(4)(hidden_layer)
    class_pred = keras.layers.Activation('sigmoid', name='class')(class_pred)

    # The first output of this model (real_fake_pred) is treated as
    # the "real / fake" predictor.
    return keras.models.Model([input_layer], [real_fake, class_pred])


def train_model(args, x, y, y_ohe):
    """Returns a trained model."""

    model = gandlf.Model(build_generator(args.nb_latent),
                         build_discriminator())

    # This part illustrates how to turn the auxiliary classifier on and off,
    # if it is needed. This approach can also be used to pre-train the
    # auxiliary parts of the discriminator.
    if args.supervised:
        loss_weights = {'src_real': 2., 'src_fake': 1.,
                        'class_real': 2., 'class_fake': 1.}
    else:
        loss_weights = {'src_real': 2., 'src_fake': 1.,
                        'class_real': 0., 'class_fake': 0.}

    optimizer = keras.optimizers.adam(0.001)
    model.compile(optimizer=optimizer, loss={
        'src_real': 'binary_crossentropy',
        'class_real': 'categorical_crossentropy',
        'src_fake': 'binary_crossentropy',
        'class_fake': 'categorical_crossentropy'
    }, metrics=['accuracy'], loss_weights=loss_weights)

    # Arguments don't just need to be passed as dictionaries. In this case,
    # the outputs correspond to [src_fake, class_fake, src_real, class_real].
    model.fit(['normal', y, x], ['zeros', y_ohe, 'ones', y_ohe],
              nb_epoch=args.nb_epoch, batch_size=args.nb_batch)

    return model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Basic XOR example using a GAN.')

    training_params = parser.add_argument_group('training params')
    training_params.add_argument('--nb_epoch', type=int, default=10,
                                 metavar='INT',
                                 help='number of training epochs')
    training_params.add_argument('--nb_batch', type=int, default=100,
                                 metavar='INT',
                                 help='number of samples per batch')
    training_params.add_argument('--supervised', default=False,
                                 action='store_true',
                                 help='if set, train as an ACGAN')

    model_params = parser.add_argument_group('model params')
    model_params.add_argument('--nb_latent', type=int, default=10,
                              metavar='INT',
                              help='dimensions in the latent vector')
    model_params.add_argument('--nb_samples', type=int, default=10000,
                              metavar='INT',
                              help='total number of training samples')

    args = parser.parse_args()

    # Get the training data.
    x, y, y_ohe = get_training_data(args.nb_samples)

    # Trains the model.
    model = train_model(args, x, y, y_ohe)

    ##### Evaluates the trained model and prints a bunch of stuff. #####

    print('\n:: Input Data ::')
    print(x[:10])

    print('\n:: Target Data ::')
    print(np.cast['int32'](y[:10]))

    if args.supervised:
        print('\n:: Predictions for Real Data ::')
        preds = np.argmax(model.predict([x[:10]])[1], -1)
        print(preds.reshape((-1, 1)))

    print('\n:: Generated Input Data (Knowing Target Data) ::')
    p = model.sample(['normal', y[:10]])
    print(p)

    if args.supervised:
        print('\n:: Predictions for Generated Data ::')
        preds = np.argmax(model.predict([p])[1], -1)
        print(preds.reshape((-1, 1)))
