import numpy as np
import tensorflow as tf

from models import Encoder, Decoder, Discriminator

from utils import TINY


class AAE(object):
    """
    INPUTS:
        X: images
        y_labels: number of classes and +1 for unlabelled images
        z_input: images drawing from a prior (either from `q_z` or `p_z`)

        p_z: `true` images draw from a prior z' ( a standard normal distribution )
        q_z: `fake` images draw from a prior z  ( generated by encoder )

        *AAE will encourage q(z) to match to the whole distribution of p(z).

    LOSS:
        tf.nn.sigmoid_cross_entropy_with_logits:
            t * -log(sigmoid(x)) + (1 - t) * -log(1 - sigmoid(x))    x: logits, t: labels

        Reconstruction Loss:
            1. MSE

        Generator Loss:
            1. minimize:  log(1 - sigmoid(D(q_z)))
            2. minimize:  -log(sigmoid(D(q_z)))

        Discriminator Loss:
            1. minimize:  -log(sigmoid(D(z'))) - log(1 - sigmoid(D(z)))

    """

    def __init__(self, input_dim, z_dim, num_classes, batch_size, learning_rate):
        self.input_dim = input_dim
        self.z_dim = z_dim
        self.num_classes = num_classes
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.step = 0

        self.X = tf.placeholder(dtype=tf.float32, shape=(None, self.input_dim), name='X_inputs')
        self.y_labels = tf.placeholder(tf.float32, shape=(None, self.num_classes + 1), name='y_labels')
        self.z_inputs = tf.placeholder(dtype=tf.float32, shape=(None, self.z_dim), name='z_inputs')

        self.encoder = Encoder(self.z_dim)
        self.decoder = Decoder(self.z_dim)
        self.discriminator = Discriminator(self.z_dim, self.num_classes)  # input dimension is the concatenation of `z_dim` and `sample`  and  `+1` for unlabelled images

    def build(self, G_type=1):

        self._build_VAE_network()
        self._build_GAN_network(G_type)

        self._build_train_ops()

        tf.get_variable_scope().reuse_variables()
        self.latent_space = self.encoder(self.X, is_training=False)
        self.generated_imgs = self.decoder(self.z_inputs, is_training=False)

    def _build_VAE_network(self):
        self.q_z = self.encoder(self.X, is_training=True)
        self.recon_imgs = self.decoder(self.q_z, is_training=True)

        self.recon_loss = tf.reduce_mean(tf.reduce_sum(tf.square(self.recon_imgs - self.X), axis=1))

        self.recon_loss_summary = tf.summary.scalar('Reconstruct_Loss', self.recon_loss)

    def _build_GAN_network(self, G_type):

        with tf.variable_scope(tf.get_variable_scope()):  # Only reuse variables in Discriminator

            fake_logits = self.discriminator(self.q_z, self.y_labels, is_training=True)
            tf.get_variable_scope().reuse_variables()
            true_logits = self.discriminator(self.z_inputs, self.y_labels, is_training=True)

            self.L_D = -tf.reduce_mean(tf.log(tf.sigmoid(true_logits) + TINY) + tf.log(1. - tf.sigmoid(fake_logits) + TINY))
            self.L_D_summary = tf.summary.scalar('Discriminator_Loss', self.L_D)

            if G_type == 1:
                self.L_G = tf.reduce_mean(1. - tf.log(tf.sigmoid(fake_logits) + TINY))
            elif G_type == 2:
                self.L_G = -tf.reduce_mean(tf.log(tf.sigmoid(fake_logits) + TINY))

            self.L_G_summary = tf.summary.scalar('Generator_Loss', self.L_G)

    def _build_train_ops(self):
        encoder_train_vars = self.encoder.get_variables()
        decoder_train_vars = self.decoder.get_variables()
        disc_train_vars = self.discriminator.get_variables()

        self.vae_train_op = tf.train.AdamOptimizer(self.learning_rate).minimize(self.recon_loss, var_list=encoder_train_vars + decoder_train_vars)
        self.disc_train_op = tf.train.AdamOptimizer(self.learning_rate).minimize(self.L_D, var_list=disc_train_vars)
        self.gen_train_op = tf.train.GradientDescentOptimizer(self.learning_rate).minimize(self.L_G, var_list=encoder_train_vars)

    def _sample_StandarddNormal(self, shape):
        return np.random.standard_normal(size=shape)

    def _sample_Guassian(self):
        pass

    def train_VAE(self, X, sess, writer=None):

        _, recon_loss, summary = sess.run([self.vae_train_op, self.recon_loss, self.recon_loss_summary], feed_dict={self.X: X})

        if writer:
            writer.add_summary(summary, self.step)

        return recon_loss

    def train_GENERATOR(self, X, y, sess, writer=None):
        feed_dict = {
            self.X: X,
            self.y_labels: y
        }

        _, gen_loss, summary = sess.run([self.gen_train_op, self.L_G, self.L_G_summary], feed_dict=feed_dict)

        if writer:
            writer.add_summary(summary, self.step)

        return gen_loss

    def train_DISCRIMINATOR(self, X, y, sess, writer=None):
        p_z = self._sample_StandarddNormal(shape=(self.batch_size, self.z_dim))

        feed_dict = {
            self.X: X,
            self.y_labels: y,
            self.z_inputs: p_z  # `z_inputs` as the prior p(z)
        }

        _, disc_loss, summary = sess.run([self.disc_train_op, self.L_D, self.L_D_summary], feed_dict=feed_dict)

        if writer:
            writer.add_summary(summary, self.step)

        return disc_loss

    def get_latent_space(self, sess, X):
        """
        Return the lantent space
        """
        return sess.run(self.latent_space, feed_dict={self.X: X})

    def get_reconstructed_images(self, sess, X):
        """
        Reconstruct the given images through the VAE network
        """
        return sess.run(self.recon_imgs, feed_dict={self.X: X})

    def get_generated_images(self, sess, q_z=None):
        """
        Generate data by sampling from the latent space.
        """

        if q_z is None:
            q_z = np.random.standard_normal([self.batch_size, self.z_dim])

        feed_dict = {
            self.z_inputs: q_z  # `z_inputs` as the prior q(z)
        }

        return sess.run(self.generated_imgs, feed_dict=feed_dict)
