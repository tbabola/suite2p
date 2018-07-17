import numpy as np
from scipy import signal

def conv2(s1, sig, axes=None):
    if axes is None:
        axes = np.arange(0,len(sig))
    s1 = np.array(s1).astype(np.float32)
    sdim = s1.ndim
    if len(axes) > 1:
        if isinstance(sig, (int, float)):
            sig = sig*np.ones((len(axes),),np.float32)
        elif len(sig) != len(axes):
            raise ValueError('number of axes different from number of smoothing constants')
        
    sig = np.array(sig).astype(np.float32)
    ns = s1.shape[0]
    flat = np.ones((ns,),np.float32)
    for j in range(0,sdim-1):
        flat = np.expand_dims(flat,axis=j+1)
    
    sfilt = s1
    for i in axes:
        dims = np.arange(-1,sdim)
        dims[0] = i
        dims = np.delete(dims, [i+1])
        print(dims)
        sfilt = np.transpose(sfilt, dims)
        tmax = np.ceil(4*sig[i])
        dt = np.arange(-tmax,tmax)
        gaus = np.exp(-dt**2 / (2*sig[i]**2))
        gaus /= gaus.sum()
        for j in range(0,sdim-1):
            gaus = np.expand_dims(gaus,axis=j+1)
        sfilt = signal.convolve(sfilt, gaus, mode='full')
        snorm = signal.convolve(flat, gaus, mode='full')
        if sfilt.shape[0] > ns:
            icent = np.floor(sfilt.shape[0]/2) - np.floor(ns/2)
            inds  = (icent + np.arange(0,ns)).astype(np.int32)
            sfilt = sfilt[inds,:]
            snorm = snorm[inds]
        sfilt = sfilt / snorm
        dims = np.arange(1,sdim)
        dims = np.insert(dims, [i], 0)
        print(dims)
        sfilt = np.transpose(sfilt, dims)
        
    return sfilt

def conv_circ(s1, sig, axes=None):
    return s1
    