from os import path
import time

import numpy as np
from tqdm import tqdm

from .. import io
from . import nonrigid
from .register import compute_reference_image, prepare_refAndMasks, \
    register_binary_to_ref, apply_shifts_to_binary, compute_crop


def register_binary(ops, refImg=None, raw=True):
    """ main registration function

    if ops is a list of dictionaries, each will be registered separately

    Parameters
    ----------

    ops : dictionary or list of dicts
        'Ly', 'Lx', 'batch_size', 'align_by_chan', 'nonrigid'
        (optional 'keep_movie_raw', 'raw_file')

    refImg : 2D array (optional, default None)

    raw : bool (optional, default True)
        use raw_file for registration if available, if False forces reg_file to be used

    Returns
    --------

    ops : dictionary
        'nframes', 'yoff', 'xoff', 'corrXY', 'yoff1', 'xoff1', 'corrXY1', 'badframes'


    """
    if (type(ops) is list) or (type(ops) is np.ndarray):
        for op in ops:
            op = register_binary(op)
        return ops

    # make blocks for nonrigid
    if ops['nonrigid']:
        ops = nonrigid.make_blocks(ops)

    if not ops['frames_include'] == -1:
        ops['nframes'] = min((ops['nframes'], ops['frames_include']))
    else:
        nbytes = path.getsize(ops['raw_file'] if ops.get('keep_movie_raw') and path.exists(ops['raw_file']) else ops['reg_file'])
        ops['nframes'] = int(nbytes / (2 * ops['Ly'] * ops['Lx']))

    print('registering %d frames'%ops['nframes'])
    # check number of frames and print warnings
    if ops['nframes']<50:
        raise Exception('ERROR: the total number of frames should be at least 50 ')
    if ops['nframes']<200:
        print('WARNING: number of frames is below 200, unpredictable behaviors may occur')

    # get binary file paths
    if raw:
        raw = ('keep_movie_raw' in ops and ops['keep_movie_raw'] and
                'raw_file' in ops and path.isfile(ops['raw_file']))
        raw_file_align = []
        raw_file_alt = []
        reg_file_align = []
        reg_file_alt = []
        if raw:
            if ops['nchannels'] > 1:
                if ops['functional_chan'] == ops['align_by_chan']:
                    raw_file_align = ops['raw_file']
                    raw_file_alt = ops['raw_file_chan2']
                    reg_file_align = ops['reg_file']
                    reg_file_alt = ops['reg_file_chan2']
                else:
                    raw_file_align = ops['raw_file_chan2']
                    raw_file_alt = ops['raw_file']
                    reg_file_align = ops['reg_file_chan2']
                    reg_file_alt = ops['reg_file']
            else:
                raw_file_align = ops['raw_file']
                reg_file_align = ops['reg_file']
        else:
            if ops['nchannels'] > 1:
                if ops['functional_chan'] == ops['align_by_chan']:
                    reg_file_align = ops['reg_file']
                    reg_file_alt = ops['reg_file_chan2']
                else:
                    reg_file_align = ops['reg_file_chan2']
                    reg_file_alt = ops['reg_file']
            else:
                reg_file_align = ops['reg_file']


    # compute reference image
    if refImg is not None:
        print('NOTE: user reference frame given')
    else:
        t0 = time.time()
        refImg, bidi = compute_reference_image(ops, raw_file_align if raw else reg_file_align)
        ops['bidiphase'] = bidi
        print('Reference frame, %0.2f sec.'%(time.time()-t0))
    ops['refImg'] = refImg


    # register binary to reference image
    refAndMasks = prepare_refAndMasks(refImg, ops)
    mean_img = np.zeros((ops['Ly'], ops['Lx']))
    for k, (offsets, data) in tqdm(enumerate(register_binary_to_ref(
        nbatch=ops['batch_size'],
        Ly=ops['Ly'],
        Lx=ops['Lx'],
        nframes=ops['nframes'],
        ops=ops,
        refAndMasks=refAndMasks,
        reg_file_align=reg_file_align,
        raw_file_align=raw_file_align,
    ))):
        if ops['reg_tif']:
            fname = io.generate_tiff_filename(
                functional_chan=ops['functional_chan'],
                align_by_chan=ops['align_by_chan'],
                save_path=ops['save_path'],
                k=k,
                ichan=True
            )
            io.save_tiff(data=data, fname=fname)

        mean_img += data.sum(axis=0) / ops['nframes']

    # mean image across all frames

    mean_img_key = 'meanImg' if ops['nchannels'] == 1 or ops['functional_chan'] == ops['align_by_chan'] else 'meanImage_chan2'
    ops[mean_img_key] = mean_img

    if ops['nchannels'] > 1:
        t0 = time.time()
        for k, (mean_img, data) in enumerate(apply_shifts_to_binary(
            batch_size=ops['batch_size'],
            Ly=ops['Ly'],
            Lx=ops['Lx'],
            nframes=ops['nframes'],
            is_nonrigid=ops['nonrigid'],
            bidiphase_value=ops['bidiphase'],
            bidi_corrected=ops['bidi_corrected'],
            nblocks=ops['nblocks'],
            xblock=ops['xblock'],
            yblock=ops['yblock'],
            offsets=offsets,
            reg_file_alt=reg_file_alt,
            raw_file_alt=raw_file_alt,
        )):

            # write registered tiffs
            if ops['reg_tif_chan2']:
                fname = io.generate_tiff_filename(
                    functional_chan=ops['functional_chan'],
                    align_by_chan=ops['align_by_chan'],
                    save_path=ops['save_path'],
                    k=k,
                    ichan=False
                )
                io.save_tiff(data=data, fname=fname)

        print('Registered second channel in %0.2f sec.' % (time.time() - t0))
        meanImg_key = 'meanImag' if ops['functional_chan'] != ops['align_by_chan'] else 'meanImg_chan2'
        ops[meanImg_key] = mean_img / (k + 1)

    if 'yoff' not in ops:
        nframes = ops['nframes']
        ops['yoff'] = np.zeros((nframes,), np.float32)
        ops['xoff'] = np.zeros((nframes,), np.float32)
        ops['corrXY'] = np.zeros((nframes,), np.float32)
        if ops['nonrigid']:
            nb = ops['nblocks'][0] * ops['nblocks'][1]
            ops['yoff1'] = np.zeros((nframes, nb), np.float32)
            ops['xoff1'] = np.zeros((nframes, nb), np.float32)
            ops['corrXY1'] = np.zeros((nframes, nb), np.float32)

    ops['yoff'] += offsets[0]
    ops['xoff'] += offsets[1]
    ops['corrXY'] += offsets[2]
    if ops['nonrigid']:
        ops['yoff1'] += offsets[3]
        ops['xoff1'] += offsets[4]
        ops['corrXY1'] += offsets[5]

    # compute valid region
    # ignore user-specified bad_frames.npy
    ops['badframes'] = np.zeros((ops['nframes'],), np.bool)
    if 'data_path' in ops and len(ops['data_path']) > 0:
        badfrfile = path.abspath(path.join(ops['data_path'][0], 'bad_frames.npy'))
        print('bad frames file path: %s'%badfrfile)
        if path.isfile(badfrfile):
            badframes = np.load(badfrfile)
            badframes = badframes.flatten().astype(int)
            ops['badframes'][badframes] = True
            print('number of badframes: %d'%ops['badframes'].sum())

    # return frames which fall outside range
    ops = compute_crop(ops)

    if not raw:
        ops['bidi_corrected'] = True

    if 'ops_path' in ops:
        np.save(ops['ops_path'], ops)
    return ops
