'''
    File name: augment.py
    Common routines for image data augmentation prior to input into training
    or validation model. We only use a small subset of these for this project.
    	Based on code samples from: https://github.com/pytorch/vision/tree/master/torchvision
    Python Version: 3.6.1

'''

from __future__ import division
import torch
import math
import random
from PIL import Image, ImageOps
from PIL import Image, ImageOps, ImageChops
from skimage.transform import warp, AffineTransform
import numpy as np
import numbers
import types

class Compose(object):
    """ Composes several transforms together.
    For example:
    >>> transforms.Compose([
    >>>     transforms.CenterCrop(10),
    >>>     transforms.ToTensor(),
    >>>  ])
    """

    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, img):
        for t in self.transforms:
            img = t(img)
        return img


class ToTensor(object):
    """ Converts a PIL.Image (RGB) or numpy.ndarray (H x W x C) in the range [0, 255]
    to a torch.FloatTensor of shape (C x H x W) in the range [0.0, 1.0] """

    def __call__(self, pic):
        if isinstance(pic, np.ndarray):
            # handle numpy array
            img = torch.from_numpy(pic)
        else:
            # handle PIL Image
            img = torch.ByteTensor(
                torch.ByteStorage.from_buffer(pic.tobytes()))
            img = img.view(pic.size[1], pic.size[0], len(pic.mode))
            # put it from HWC to CHW format
            # yikes, this transpose takes 80% of the loading time/CPU
            img = img.transpose(0, 1).transpose(0, 2).contiguous()
        return img.float().div(255)


class ToPILImage(object):
    """ Converts a torch.*Tensor of range [0, 1] and shape C x H x W
    or numpy ndarray of dtype=uint8, range[0, 255] and shape H x W x C
    to a PIL.Image of range [0, 255]
    """

    def __call__(self, pic):
        if isinstance(pic, np.ndarray):
            # handle numpy array
            img = Image.fromarray(pic)
        else:
            npimg = pic.mul(255).byte().numpy()
            npimg = np.transpose(npimg, (1, 2, 0))
            img = Image.fromarray(npimg)
        return img


class Normalize(object):
    """ Given mean: (R, G, B) and std: (R, G, B),
    will normalize each channel of the torch.*Tensor, i.e.
    channel = (channel - mean) / std
    """

    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, img):
        tensor = img.clone()
        # TODO: make efficient
        for t, m, s in zip(tensor, self.mean, self.std):
            t.sub_(m).div_(s)
        return tensor


class Scale(object):
    """ Rescales the input PIL.Image to the given 'size'.
    'size' will be the size of the smaller edge.
    For example, if height > width, then image will be
    rescaled to (size * height / width, size)
    size: size of the smaller edge
    interpolation: Default: PIL.Image.BILINEAR
    """

    def __init__(self, size, interpolation=Image.BILINEAR):
        self.size = size
        self.interpolation = interpolation

    def __call__(self, img):
        w, h = img.size
        if (w <= h and w == self.size) or (h <= w and h == self.size):
            return img
        if w < h:
            ow = self.size
            oh = int(self.size * h / w)
            return img.resize((ow, oh), self.interpolation)
        else:
            oh = self.size
            ow = int(self.size * w / h)
            return img.resize((ow, oh), self.interpolation)

class AnisotropicScale(object):
    """Rescales the input PIL.Image to the given 'size'.
    Unlike torchvision.transforms.Scale, this transform directly resizes the
    image to the given size without necessarily preserving aspect ratio.
    size: new image size (width, height)
    interpolation: Default: PIL.Image.BILINEAR
    """

    def __init__(self, size, interpolation=Image.BILINEAR):
        self.size = size
        self.interpolation = interpolation

    def __call__(self, img):
        w, h = img.size
        ow, oh = self.size
        return img.resize((ow, oh), self.interpolation)

class CenterCrop(object):
    """Crops the given PIL.Image at the center to have a region of
    the given size. size can be a tuple (target_height, target_width)
    or an integer, in which case the target will be of a square shape (size, size)
    """

    def __init__(self, size):
        if isinstance(size, numbers.Number):
            self.size = (int(size), int(size))
        else:
            self.size = size

    def __call__(self, img):
        w, h = img.size
        th, tw = self.size
        x1 = int(round((w - tw) / 2.))
        y1 = int(round((h - th) / 2.))
        return img.crop((x1, y1, x1 + tw, y1 + th))


class Pad(object):
    """Pads the given PIL.Image on all sides with the given "pad" value"""

    def __init__(self, padding, fill=0):
        assert isinstance(padding, numbers.Number)
        assert isinstance(fill, numbers.Number)
        self.padding = padding
        self.fill = fill

    def __call__(self, img):
        return ImageOps.expand(img, border=self.padding, fill=self.fill)


class ScalePad(object):
    """ Rescales the input PIL.Image to the given 'size' (int, int).
        Maintains aspect ratio by padding with zeros.
    """

    def __init__(self, size):
        self.size = size

    def __call__(self, image):

        image.thumbnail(self.size, Image.ANTIALIAS)
        image_size = image.size

        thumb = image.crop( (0, 0, self.size[0], self.size[1]) )

        offset_x = max( (self.size[0] - image_size[0]) // 2, 0 )
        offset_y = max( (self.size[1] - image_size[1]) // 2, 0 )

        return ImageChops.offset(thumb, offset_x, offset_y)

class Lambda(object):
    """Applies a lambda as a transform"""

    def __init__(self, lambd):
        assert type(lambd) is types.LambdaType
        self.lambd = lambd

    def __call__(self, img):
        return self.lambd(img)


class RandomCrop(object):
    """Crops the given PIL.Image at a random location to have a region of
    the given size. size can be a tuple (target_height, target_width)
    or an integer, in which case the target will be of a square shape (size, size)
    """

    def __init__(self, size, padding=0):
        if isinstance(size, numbers.Number):
            self.size = (int(size), int(size))
        else:
            self.size = size
        self.padding = padding

    def __call__(self, img):
        if self.padding > 0:
            img = ImageOps.expand(img, border=self.padding, fill=0)

        w, h = img.size
        th, tw = self.size
        if w == tw and h == th:
            return img

        x1 = random.randint(0, w - tw)
        y1 = random.randint(0, h - th)
        return img.crop((x1, y1, x1 + tw, y1 + th))


class RandomHorizontalFlip(object):
    """Randomly horizontally flips the given PIL.Image with a probability of 0.5
    """

    def __call__(self, img):
        if random.random() < 0.5:
            return img.transpose(Image.FLIP_LEFT_RIGHT)
        return img


class RandomSizedCrop(object):
    """Random crop the given PIL.Image to a random size of (0.08 to 1.0) of the original size
    and and a random aspect ratio of 3/4 to 4/3 of the original aspect ratio
    This is popularly used to train the Inception networks
    size: size of the smaller edge
    interpolation: Default: PIL.Image.BILINEAR
    """

    def __init__(self, size, interpolation=Image.BILINEAR):
        self.size = size
        self.interpolation = interpolation

    def __call__(self, img):
        for attempt in range(10):
            area = img.size[0] * img.size[1]
            target_area = random.uniform(0.08, 1.0) * area
            aspect_ratio = random.uniform(3. / 4, 4. / 3)

            w = int(round(math.sqrt(target_area * aspect_ratio)))
            h = int(round(math.sqrt(target_area / aspect_ratio)))

            if random.random() < 0.5:
                w, h = h, w

            if w <= img.size[0] and h <= img.size[1]:
                x1 = random.randint(0, img.size[0] - w)
                y1 = random.randint(0, img.size[1] - h)

                img = img.crop((x1, y1, x1 + w, y1 + h))
                assert(img.size == (w, h))

                return img.resize((self.size, self.size), self.interpolation)

        # Fallback
        scale = Scale(self.size, interpolation=self.interpolation)
        crop = CenterCrop(self.size)
        return crop(scale(img))


class Lighting(object):
    """Lighting noise(AlexNet - style PCA - based noise)"""

    def __init__(self, alphastd, eigval, eigvec):
        self.alphastd = alphastd
        self.eigval = eigval
        self.eigvec = eigvec

    def __call__(self, img):
        if self.alphastd == 0:
            return img

        alpha = img.new().resize_(3).normal_(0, self.alphastd)
        rgb = self.eigvec.type_as(img).clone()\
            .mul(alpha.view(1, 3).expand(3, 3))\
            .mul(self.eigval.view(1, 3).expand(3, 3))\
            .sum(1).squeeze()

        return img.add(rgb.view(3, 1, 1).expand_as(img))


class Grayscale(object):

    def __call__(self, img):
        gs = img.clone()
        gs[0].mul_(0.299).add_(0.587, gs[1]).add_(0.114, gs[2])
        gs[1].copy_(gs[0])
        gs[2].copy_(gs[0])
        return gs


class Saturation(object):

    def __init__(self, var):
        self.var = var

    def __call__(self, img):
        gs = Grayscale()(img)
        alpha = random.uniform(0, self.var)
        return img.lerp(gs, alpha)


class Brightness(object):

    def __init__(self, var):
        self.var = var

    def __call__(self, img):
        gs = img.new().resize_as_(img).zero_()
        alpha = random.uniform(0, self.var)
        return img.lerp(gs, alpha)


class Contrast(object):

    def __init__(self, var):
        self.var = var

    def __call__(self, img):
        gs = Grayscale()(img)
        gs.fill_(gs.mean())
        alpha = random.uniform(0, self.var)
        return img.lerp(gs, alpha)


class RandomOrder(object):
    """ Composes several transforms together in random order.
    """

    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, img):
        if self.transforms is None:
            return img
        order = torch.randperm(len(self.transforms))
        for i in order:
            img = self.transforms[i](img)
        return img


class ColorJitter(RandomOrder):

    def __init__(self, brightness=0.4, contrast=0.4, saturation=0.4):
        self.transforms = []
        if brightness != 0:
            self.transforms.append(Brightness(brightness))
        if contrast != 0:
            self.transforms.append(Contrast(contrast))
        if saturation != 0:
            self.transforms.append(Saturation(saturation))


class RandomAffineTransform(object):
    def __init__(self,
                 scale_range,
                 rotation_range,
                 shear_range,
                 translation_range
                 ):
        self.scale_range = scale_range
        self.rotation_range = rotation_range
        self.shear_range = shear_range
        self.translation_range = translation_range

    def __call__(self, img):
        img_data = np.array(img)
        h, w, n_chan = img_data.shape
        scale_x = np.random.uniform(*self.scale_range)
        scale_y = np.random.uniform(*self.scale_range)
        scale = (scale_x, scale_y)
        rotation = np.random.uniform(*self.rotation_range)
        shear = np.random.uniform(*self.shear_range)
        translation = (
            np.random.uniform(*self.translation_range) * w,
            np.random.uniform(*self.translation_range) * h
        )
        af = AffineTransform(scale=scale, shear=shear, rotation=rotation, translation=translation)
        img_data1 = warp(img_data, af.inverse)
        img1 = Image.fromarray(np.uint8(img_data1 * 255))
        return img1
