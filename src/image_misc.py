#! /usr/bin/env python

import cv2
import numpy as np
import skimage
import skimage.io

from misc import WithTimer



def norm01(arr):
    arr = arr.copy()
    arr -= arr.min()
    arr /= arr.max() + 1e-10
    return arr



def norm01c(arr, center):
    '''Maps the input range to [0,1] such that the center value maps to .5'''
    arr = arr.copy()
    arr -= center
    arr /= max(2 * arr.max(), -2 * arr.min()) + 1e-10
    arr += .5
    assert arr.min() >= 0
    assert arr.max() <= 1
    return arr



def norm0255(arr):
    '''Maps the input range to [0,255] as dtype uint8'''
    arr = arr.copy()
    arr -= arr.min()
    arr *= 255.0 / (arr.max() + 1e-10)
    arr = np.array(arr, 'uint8')
    return arr



def cv2_read_cap_rgb(cap, saveto = None):
    rval, frame = cap.read()
    if saveto:
        cv2.imwrite(saveto, frame)
    frame = frame[:,:,::-1]   # Convert native OpenCV BGR -> RGB
    return frame


def cv2_read_file_rgb(filename):
    im = cv2.imread(filename)
    im = im[:,:,::-1]   # Convert native OpenCV BGR -> RGB
    return im


def read_cam_frame(cap, saveto = None):
    #frame = np.array(cv2_read_cap_rgb(cap, saveto = saveto), dtype='float32')
    frame = cv2_read_cap_rgb(cap, saveto = saveto)
    frame = frame[:,::-1,:]  # flip L-R for display
    frame -= frame.min()
    frame = frame * (255.0 / (frame.max() + 1e-6))
    return frame

def crop_to_center(frame):
    # print frame.shape
    if frame.shape[0] == 480 and frame.shape[1] == 640:
        # return frame[220:460,200:440,:]
        return frame[200:460,180:440,:]
        # return frame[180:460,180:460,:]
    else:
        return crop_to_square(frame)

def get_crop_bias():
    # return (220, 200)
    return (200, 180)
    # return (180, 180)

def get_after_crop_size():
    # return (240, 240)
    return (260, 260)
    # return (280, 280)

def crop_to_square(frame):
    i_size,j_size = frame.shape[0],frame.shape[1]
    if j_size > i_size:
        # landscape
        offset = (j_size - i_size) / 2
        return frame[:,offset:offset+i_size,:]
    else:
        # portrait
        offset = (i_size - j_size) / 2
        return frame[offset:offset+j_size,:,:]

def cv2_imshow_rgb(window_name, img):
    # Convert native OpenCV BGR -> RGB before displaying
    cv2.imshow(window_name, img[:,:,::-1])
    #cv2.imshow(window_name, img)


def caffe_load_image(filename, color=True, as_uint=False):
    '''
    Copied from Caffe to simplify potential import problems.

    Load an image converting from grayscale or alpha as needed.

    Take
    filename: string
    color: flag for color format. True (default) loads as RGB while False
        loads as intensity (if image is already grayscale).

    Give
    image: an image with type np.float32 in range [0, 1]
        of size (H x W x 3) in RGB or
        of size (H x W x 1) in grayscale.
    '''
    with WithTimer('imread', quiet = True):
        if as_uint:
            img = skimage.io.imread(filename)
        else:
            img = skimage.img_as_float(skimage.io.imread(filename)).astype(np.float32)
    if img.ndim == 2:
        img = img[:, :, np.newaxis]
        if color:
            img = np.tile(img, (1, 1, 3))
    elif img.shape[2] == 4:
        img = img[:, :, :3]
    return img

def get_tiles_height_width(n_tiles, desired_width = None):
    '''Get a height x width size that will fit n_tiles tiles.'''
    if desired_width == None:
        # square
        width = int(np.ceil(np.sqrt(n_tiles)))
        height = width
    else:
        assert isinstance(width, int)
        height = int(np.ceil(float(n_tiles) / width))
    return height,width

def tile_images(data, padsize = 1, padval = 0, c01 = False, width = None, boost_indiv = 0.0, boost_gamma = 1.0, highlights = None, single_tile = False):
    '''take an array of shape (n, height, width) or (n, height, width, channels)
    and visualize each (height, width) thing in a grid. If width = None, produce
    a square image of size approx. sqrt(n) by sqrt(n), else calculate height given width value.

    If highlights is given, it should be a list of length data.shape[0] with each element a color triple or None'''

    data = tile_images_normalize(data, c01 = c01, boost_indiv = boost_indiv,  boost_gamma = boost_gamma, single_tile = single_tile)
    (height,width), data = tile_images_make_tiles(data, padsize = padsize, padval = padval, width = width, highlights = highlights)
    return (height,width), data

def tile_images_normalize(data, c01 = False, boost_indiv = 0.0,  boost_gamma = 1.0, single_tile = False, scale_range = 1.0, neg_pos_colors = None):
    data = data.copy()
    if single_tile:
        # promote 2D image -> 3D batch (01 -> b01) or 3D image -> 4D batch (01c -> b01c OR c01 -> bc01)
        data = data[np.newaxis]
    if c01:
        # Convert bc01 -> b01c
        assert len(data.shape) == 4, 'expected bc01 data'
        data = data.transpose(0, 2, 3, 1)

    if neg_pos_colors:
        neg_clr, pos_clr = neg_pos_colors
        neg_clr = np.array(neg_clr).reshape((1,3))
        pos_clr = np.array(pos_clr).reshape((1,3))
        # Keep 0 at 0
        data /= max(data.max(), -data.min()) + 1e-10     # Map data to [-1, 1]

        #data += .5 * scale_range  # now in [0, scale_range]
        #assert data.min() >= 0
        #assert data.max() <= scale_range
        if len(data.shape) == 3:
            data = data.reshape(data.shape + (1,))
        assert data.shape[3] == 1, 'neg_pos_color only makes sense if color data is not provided (channels should be 1)'
        data = np.dot((data > 0) * data, pos_clr) + np.dot((data < 0) * -data, neg_clr)

    data -= data.min()
    data *= scale_range / (data.max() + 1e-10)

    # sqrt-scale (0->0, .1->.3, 1->1)
    assert boost_indiv >= 0 and boost_indiv <= 1, 'boost_indiv out of range'
    #print 'using boost_indiv:', boost_indiv
    if boost_indiv > 0:
        if len(data.shape) == 4:
            mm = (data.max(-1).max(-1).max(-1) + 1e-10) ** -boost_indiv
        else:
            mm = (data.max(-1).max(-1) + 1e-10) ** -boost_indiv
        data = (data.T * mm).T
    if boost_gamma != 1.0:
        data = data ** boost_gamma
    #if False:
    #    print 'SQRT gamma'
    #    data = data ** .5
    #assert False

    # Promote single-channel data to 3 channel color
    if len(data.shape) == 3:
        # b01 -> b01c
        data = np.tile(data[:,:,:,np.newaxis], 3)

    return data

def tile_images_make_tiles(data, padsize=1, padval=0, width=None, highlights = None):
    height,width = get_tiles_height_width(data.shape[0], desired_width = width)

    # Old one-way padding, no highlights
    #padding = ((0, width*height - data.shape[0]), (0, padsize), (0, padsize)) + ((0, 0),) * (data.ndim - 3)
    #data = np.pad(data, padding, mode='constant', constant_values=(padval, padval))

    # New two-way padding with highlights
    #padding = ((0, width*height - data.shape[0]), (padsize, padsize), (padsize, padsize)) + ((0, 0),) * (data.ndim - 3)
    #print 'tile_images: data min,max =', data.min(), data.max()
    #padder = SmartPadder()
    ##data = np.pad(data, padding, mode=jy_pad_fn)
    #data = np.pad(data, padding, mode=padder.pad_function)
    #print 'padder.calls =', padder.calls

    # New new way, two-way padding with highlights
    if highlights is not None:
        assert len(highlights) == data.shape[0]
    padding = ((0, width*height - data.shape[0]), (padsize, padsize), (padsize, padsize)) + ((0, 0),) * (data.ndim - 3)

    # First pad with constant vals
    try:
        len(padval)
    except:
        padval = tuple((padval,))
    assert len(padval) in (1,3), 'padval should be grayscale (len 1) or color (len 3)'
    if len(padval) == 1:
        data = np.pad(data, padding, mode='constant', constant_values=(padval, padval))
    else:
        data = np.pad(data, padding, mode='constant', constant_values=(0, 0))
        for cc in (0,1,2):
            # Replace 0s with proper color in each channel
            data[:padding[0][0],  :, :, cc] = padval[cc]
            if padding[0][1] > 0:
                data[-padding[0][1]:, :, :, cc] = padval[cc]
            data[:, :padding[1][0],  :, cc] = padval[cc]
            if padding[1][1] > 0:
                data[:, -padding[1][1]:, :, cc] = padval[cc]
            data[:, :, :padding[2][0],  cc] = padval[cc]
            if padding[2][1] > 0:
                data[:, :, -padding[2][1]:, cc] = padval[cc]
    if highlights is not None:
        # Then highlight if necessary
        for ii,highlight in enumerate(highlights):
            if highlight is not None:
                data[ii,:padding[1][0],:,:] = highlight
                if padding[1][1] > 0:
                    data[ii,-padding[1][1]:,:,:] = highlight
                data[ii,:,:padding[2][0],:] = highlight
                if padding[2][1] > 0:
                    data[ii,:,-padding[2][1]:,:] = highlight



    # tile the filters into an image
    data = data.reshape((height, width) + data.shape[1:]).transpose((0, 2, 1, 3) + tuple(range(4, data.ndim + 1)))
    data = data.reshape((height * data.shape[1], width * data.shape[3]) + data.shape[4:])
    data = data[0:-padsize, 0:-padsize]  # remove excess padding

    return (height,width), data

def to_255(vals_01):
    '''Convert vals in [0,1] to [0,255]'''
    try:
        ret = [v*255 for v in vals_01]
        if type(vals_01) is tuple:
            return tuple(ret)
        else:
            return ret
    except TypeError:
        # Not iterable (single int or float)
        return vals_01*255

def ensure_uint255_and_resize_to_fit(img, out_max_shape,
                                     shrink_interpolation = cv2.INTER_LINEAR,
                                     grow_interpolation = cv2.INTER_NEAREST):
    as_uint255 = ensure_uint255(img)
    return resize_to_fit(as_uint255, out_max_shape,
                         dtype_out = 'uint8',
                         shrink_interpolation = shrink_interpolation,
                         grow_interpolation = grow_interpolation)

def ensure_uint255(arr):
    '''If data is float, multiply by 255 and convert to uint8. Else leave as uint8.'''
    if arr.dtype == 'uint8':
        return arr
    elif arr.dtype in ('float32', 'float64'):
        #print 'extra check...'
        #assert arr.max() <= 1.1
        return np.array(arr * 255, dtype = 'uint8')
    else:
        raise Exception('ensure_uint255 expects uint8 or float input but got %s with range [%g,%g,].' % (arr.dtype, arr.min(), arr.max()))

def ensure_float01(arr, dtype_preference = 'float32'):
    '''If data is uint, convert to float and divide by 255. Else leave at float.'''
    if arr.dtype == 'uint8':
        #print 'extra check...'
        #assert arr.max() <= 256
        return np.array(arr, dtype = dtype_preference) / 255
    elif arr.dtype in ('float32', 'float64'):
        return arr
    else:
        raise Exception('ensure_float01 expects uint8 or float input but got %s with range [%g,%g,].' % (arr.dtype, arr.min(), arr.max()))

def resize_to_fit(img, out_max_shape,
                  dtype_out = None,
                  shrink_interpolation = cv2.INTER_LINEAR,
                  grow_interpolation = cv2.INTER_NEAREST):
    '''Resizes to fit within out_max_shape. If ratio is different,
    returns an image that fits but is smaller along one of the two
    dimensions.

    If one of the out_max_shape dimensions is None, then use only the other dimension to perform resizing.

    Timing info on MBP Retina with OpenBlas:
     - conclusion: uint8 is always tied or faster. float64 is slower.

    Scaling down:
    In [79]: timeit.Timer('resize_to_fit(aa, (200,200))', setup='from caffevis.app import resize_to_fit; import numpy as np; aa = np.array(np.random.uniform(0,255,(1000,1000,3)), dtype="uint8")').timeit(100)
    Out[79]: 0.04950380325317383

    In [77]: timeit.Timer('resize_to_fit(aa, (200,200))', setup='from caffevis.app import resize_to_fit; import numpy as np; aa = np.array(np.random.uniform(0,255,(1000,1000,3)), dtype="float32")').timeit(100)
    Out[77]: 0.049156904220581055

    In [76]: timeit.Timer('resize_to_fit(aa, (200,200))', setup='from caffevis.app import resize_to_fit; import numpy as np; aa = np.array(np.random.uniform(0,255,(1000,1000,3)), dtype="float64")').timeit(100)
    Out[76]: 0.11808204650878906

    Scaling up:
    In [68]: timeit.Timer('resize_to_fit(aa, (2000,2000))', setup='from caffevis.app import resize_to_fit; import numpy as np; aa = np.array(np.random.uniform(0,255,(1000,1000,3)), dtype="uint8")').timeit(100)
    Out[68]: 0.4357950687408447

    In [70]: timeit.Timer('resize_to_fit(aa, (2000,2000))', setup='from caffevis.app import resize_to_fit; import numpy as np; aa = np.array(np.random.uniform(0,255,(1000,1000,3)), dtype="float32")').timeit(100)
    Out[70]: 1.3411099910736084

    In [73]: timeit.Timer('resize_to_fit(aa, (2000,2000))', setup='from caffevis.app import resize_to_fit; import numpy as np; aa = np.array(np.random.uniform(0,255,(1000,1000,3)), dtype="float64")').timeit(100)
    Out[73]: 2.6078310012817383
    '''

    if dtype_out is not None and img.dtype != dtype_out:
        dtype_in_size = img.dtype.itemsize
        dtype_out_size = np.dtype(dtype_out).itemsize
        convert_early = (dtype_out_size < dtype_in_size)
        convert_late = not convert_early
    else:
        convert_early = False
        convert_late = False
    if out_max_shape[0] is None:
        scale = float(out_max_shape[1]) / img.shape[1]
    elif out_max_shape[1] is None:
        scale = float(out_max_shape[0]) / img.shape[0]
    else:
        scale = min(float(out_max_shape[0]) / img.shape[0],
                    float(out_max_shape[1]) / img.shape[1])

    if convert_early:
        img = np.array(img, dtype=dtype_out)
    out = cv2.resize(img,
            (int(img.shape[1] * scale), int(img.shape[0] * scale)),   # in (c,r) order
                     interpolation = grow_interpolation if scale > 1 else shrink_interpolation)
    if convert_late:
        out = np.array(out, dtype=dtype_out)
    return out

class FormattedString(object):
    def __init__(self, string, defaults, face=None, fsize=None, clr=None, thick=None, align=None, width=None):
        self.string = string
        self.face  = face  if face  else defaults['face']
        self.fsize = fsize if fsize else defaults['fsize']
        self.clr   = clr   if clr   else defaults['clr']
        self.thick = thick if thick else defaults['thick']
        self.width = width # if None: calculate width automatically
        self.align = align if align else defaults.get('align', 'left')

def cv2_typeset_text(data, lines, loc, between = ' ', string_spacing = 0, line_spacing = 0):
    '''Typesets mutliple strings on multiple lines of text, where each string may have its own formatting.

    Given:
    data: as in cv2.putText
    loc: as in cv2.putText
    lines: list of lists of FormattedString objects
    between: what to insert between each string on each line, ala str.join
    string_spacing: extra spacing to insert between strings on a line
    line_spacing: extra spacing to insert between lines

    Returns:
    locy: new y location = loc[1] + y-offset resulting from lines of text
    '''

    assert isinstance(lines, list), 'lines must be a list of lines or list of strings'
    if len(lines) == 0:
        return loc[1]
    if not isinstance(lines[0], list):
        # If a single line of text is given as a list of strings, convert to multiline format
        lines = [lines]

    locy = loc[1]

    for line in lines:
        maxy = 0
        locx = loc[0]
        for ii,fs in enumerate(line):
            last_on_line = (ii == len(line) - 1)
            if not last_on_line:
                fs.string += between
            boxsize, _ = cv2.getTextSize(fs.string, fs.face, fs.fsize, fs.thick)
            if fs.width is not None:
                if fs.align == 'right':
                    locx += fs.width - boxsize[0]
                elif fs.align == 'center':
                    locx += (fs.width - boxsize[0])/2
            cv2.putText(data, fs.string, (locx,locy), fs.face, fs.fsize, fs.clr, fs.thick)
            maxy = max(maxy, boxsize[1])
            if fs.width is not None:
                if fs.align == 'right':
                    locx += boxsize[0]
                elif fs.align == 'left':
                    locx += fs.width
                elif fs.align == 'center':
                    locx += fs.width - (fs.width - boxsize[0])/2
            else:
                locx += boxsize[0]
            locx += string_spacing
        locy += maxy + line_spacing

    return locy

def get_relative_location(input_w_h, input_x_y, target_w_h):

    target_x = round((input_x_y[0]+0.5)*float(target_w_h[0])/float(input_w_h[0]))
    target_y = round((input_x_y[1]+0.5)*float(target_w_h[1])/float(input_w_h[1]))
    return [target_x, target_y]

def is_masked(input_w_h, input_x_y, mask):

    target_x_y = get_relative_location(input_w_h, input_x_y, mask.shape)
    # print "target x y", target_x_y
    # print "mask ", mask.shape
    if mask[target_x_y[1],target_x_y[0]] == 0:
        return True
    else:
        return False

def depth_to_grayscale(depth):
    return min(round(depth*255.0/2.0),255)

def convert_depth_image_to_rgb(depth_image):
    f= np.vectorize(depth_to_grayscale)
    gray_image = f(depth_image)
    return np.repeat(gray_image, 3, axis=2)