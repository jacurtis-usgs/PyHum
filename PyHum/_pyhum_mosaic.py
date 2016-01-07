## PyHum (Python program for Humminbird(R) data processing) 
## has been developed at the Grand Canyon Monitoring & Research Center,
## U.S. Geological Survey
##
## Author: Daniel Buscombe
## Project homepage: <https://github.com/dbuscombe-usgs/PyHum>
##
##This software is in the public domain because it contains materials that originally came from 
##the United States Geological Survey, an agency of the United States Department of Interior. 
##For more information, see the official USGS copyright policy at 
##http://www.usgs.gov/visual-id/credit_usgs.html#copyright
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
## See the GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/>.

#"""
# ____        _   _                         
#|  _ \ _   _| | | |_   _ _ __ ___    _   _ 
#| |_) | | | | |_| | | | | '_ ` _ \  (_) (_)
#|  __/| |_| |  _  | |_| | | | | | |  _   _ 
#|_|    \__, |_| |_|\__,_|_| |_| |_| (_) (_)
#       |___/                               
#
#                        
#   ____ ___  ____ _____ 
#  / __ `__ \/ __ `/ __ \
# / / / / / / /_/ / /_/ /
#/_/ /_/ /_/\__,_/ .___/ 
#               /_/      
#
##+-+-+ +-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
#|b|y| |D|a|n|i|e|l| |B|u|s|c|o|m|b|e|
#+-+-+ +-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|d|b|u|s|c|o|m|b|e|@|u|s|g|s|.|g|o|v|
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#+-+-+-+-+ +-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+
#|U|.|S|.| |G|e|o|l|o|g|i|c|a|l| |S|u|r|v|e|y|
#+-+-+-+-+ +-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+

#"""

# =========================================================
# ====================== libraries ======================
# =========================================================

# operational
from __future__ import division
from scipy.io import loadmat
import os, time, sys, getopt
try:
   from Tkinter import Tk
   from tkFileDialog import askopenfilename, askdirectory
except:
   pass
from joblib import Parallel, delayed, cpu_count
import pyproj

import replace_nans
import write

import PyHum.io as io
import cPickle as pickle

# numerical
import numpy as np
import PyHum.utils as humutils
import pyresample
from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes
from scipy.spatial import cKDTree as KDTree

# plotting
import matplotlib.pyplot as plt
try:
   from mpl_toolkits.basemap import Basemap
except:
   print "Error: Basemap could not be imported"
   pass
import simplekml

# suppress divide and invalid warnings
np.seterr(divide='ignore')
np.seterr(invalid='ignore')

import warnings
warnings.filterwarnings("ignore")

#################################################
def map(humfile, sonpath, cs2cs_args = "epsg:26949", dogrid = 1, res = 0, dowrite = 0, mode=3, nn = 128, influence = 1, numstdevs=5):
         
    '''
    Create plots of the spatially referenced sidescan echograms

    Syntax
    ----------
    [] = PyHum.map(humfile, sonpath, cs2cs_args, dogrid, res, dowrite, mode, nn, influence, numstdevs)

    Parameters
    ----------
    humfile : str
       path to the .DAT file
    sonpath : str
       path where the *.SON files are
    cs2cs_args : int, *optional* [Default="epsg:26949"]
       arguments to create coordinates in a projected coordinate system
       this argument gets given to pyproj to turn wgs84 (lat/lon) coordinates
       into any projection supported by the proj.4 libraries
    dogrid : float, *optional* [Default=1]
       if 1, textures will be gridded with resolution 'res'. 
       Otherwise, point cloud will be plotted
    res : float, *optional* [Default=0]
       grid resolution of output gridded texture map
       if res=0, res will be determined automatically from the spatial resolution of 1 pixel
    dowrite: int, *optional* [Default=0]
       if 1, point cloud data from each chunk is written to ascii file
       if 0, processing times are speeded up considerably but point clouds are not available for further analysis
    mode: int, *optional* [Default=3]
       gridding mode. 1 = nearest neighbour
                      2 = inverse weighted nearest neighbour
                      3 = Gaussian weighted nearest neighbour
    nn: int, *optional* [Default=64]
       number of nearest neighbours for gridding (used if mode > 1)
    influence: float, *optional* [Default=1]
       Radius of influence used in gridding. Cut off distance in meters   
    numstdevs: int, *optional* [Default = 4]
       Threshold number of standard deviations in sidescan intensity per grid cell up to which to accept            

    
    Returns
    -------
    sonpath+'x_y_ss_raw'+str(p)+'.asc'  : text file
        contains the point cloud of easting, northing, and sidescan intensity
        of the pth chunk

    sonpath+'GroundOverlay'+str(p)+'.kml': kml file
        contains gridded (or point cloud) sidescan intensity map for importing into google earth
        of the pth chunk

    sonpath+'map'+str(p)+'.png' : 
        image overlay associated with the kml file

    '''

    # prompt user to supply file if no input file given
    if not humfile:
       print 'An input file is required!!!!!!'
       Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
       inputfile = askopenfilename(filetypes=[("DAT files","*.DAT")]) 

    # prompt user to supply directory if no input sonpath is given
    if not sonpath:
       print 'A *.SON directory is required!!!!!!'
       Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
       sonpath = askdirectory() 

    # print given arguments to screen and convert data type where necessary
    if humfile:
       print 'Input file is %s' % (humfile)

    if sonpath:
       print 'Sonar file path is %s' % (sonpath)

    if cs2cs_args:
       print 'cs2cs arguments are %s' % (cs2cs_args)

    if dogrid:
       dogrid = int(dogrid)
       if dogrid==1:
          print "Data will be gridded"      

    if res:
       res = np.asarray(res,float)
       print 'Gridding resolution: %s' % (str(res))      

    if dowrite:
       dowrite = int(dowrite)
       if dowrite==0:
          print "Point cloud data will be written to ascii file" 

    if mode:
       mode = int(mode)
       print 'Mode for gridding: %s' % (str(mode))   
       
    if nn:
       nn = int(nn)
       print 'Number of nearest neighbours for gridding: %s' % (str(nn))             

    if influence:
       influence = int(influence)
       print 'Radius of influence for gridding: %s (m)' % (str(influence))             

    if numstdevs:
       numstdevs = int(numstdevs)
       print 'Threshold number of standard deviations in sidescan intensity per grid cell up to which to accept: %s' % (str(numstdevs))             

    k = 5 #number of nearest neighbours in gridding
    noise=10 # noise threshold in dB W


    # start timer
    if os.name=='posix': # true if linux/mac or cygwin on windows
       start = time.time()
    else: # windows
       start = time.clock()

    trans =  pyproj.Proj(init=cs2cs_args)

    # if son path name supplied has no separator at end, put one on
    if sonpath[-1]!=os.sep:
       sonpath = sonpath + os.sep

    base = humfile.split('.DAT') # get base of file name for output
    base = base[0].split(os.sep)[-1]

    # remove underscores, negatives and spaces from basename
    base = humutils.strip_base(base)

    meta = loadmat(os.path.normpath(os.path.join(sonpath,base+'meta.mat')))

    esi = np.squeeze(meta['e'])
    nsi = np.squeeze(meta['n']) 
    
    theta = np.squeeze(meta['heading'])/(180/np.pi)

    # load memory mapped scans
    shape_port = np.squeeze(meta['shape_port'])
    if shape_port!='':
       if os.path.isfile(os.path.normpath(os.path.join(sonpath,base+'_data_port_lar.dat'))):
          port_fp = io.get_mmap_data(sonpath, base, '_data_port_lar.dat', 'float32', tuple(shape_port))
       else:
          port_fp = io.get_mmap_data(sonpath, base, '_data_port_la.dat', 'float32', tuple(shape_port))

    shape_star = np.squeeze(meta['shape_star'])
    if shape_star!='':
       if os.path.isfile(os.path.normpath(os.path.join(sonpath,base+'_data_star_lar.dat'))):
             star_fp = io.get_mmap_data(sonpath, base, '_data_star_lar.dat', 'float32', tuple(shape_star))
       else:
          star_fp = io.get_mmap_data(sonpath, base, '_data_star_la.dat', 'float32', tuple(shape_star))

    # time varying gain
    tvg = ((8.5*10**-5)+(3/76923)+((8.5*10**-5)/4))*meta['c']
        
    # depth correction
    dist_tvg = np.squeeze(((np.tan(np.radians(25)))*np.squeeze(meta['dep_m']))-(tvg))

    # read in range data
    R_fp = io.get_mmap_data(sonpath, base, '_data_range.dat', 'float32', tuple(shape_star))

    dx = np.arcsin(meta['c']/(1000*meta['t']*meta['f']))
    pix_m = meta['pix_m']
    c = meta['c']

    inputfiles = []
    if len(shape_star)>2:    
       for p in xrange(len(star_fp)):
          e = esi[shape_port[-1]*p:shape_port[-1]*(p+1)]
          n = nsi[shape_port[-1]*p:shape_port[-1]*(p+1)]
          t = theta[shape_port[-1]*p:shape_port[-1]*(p+1)]
          d = dist_tvg[shape_port[-1]*p:shape_port[-1]*(p+1)]
          dat_port = port_fp[p]
          dat_star = star_fp[p]
          data_R = R_fp[p]
          print "writing chunk %s " % (str(p))
          write_points(e, n, t, d, dat_port, dat_star, data_R, pix_m, res, cs2cs_args, sonpath, p, c, dx)
          inputfiles.append(os.path.normpath(os.path.join(sonpath,'x_y_ss_raw'+str(p)+'.asc')))
    else:
       print "writing chunk %s " % (str(p))
       write_points(esi, nsi, theta, dist_tvg, port_fp, star_fp, R_fp, meta['pix_m'], res, cs2cs_args, sonpath, 0, c, dx)
       inputfiles.append(os.path.normpath(os.path.join(sonpath,'x_y_ss_raw'+str(p)+'.asc')))         
          
    trans =  pyproj.Proj(init=cs2cs_args)

    # D, R, h, t
    print "reading points from %s files" % (str(len(inputfiles)))
    X,Y,S,D,R,h,t,i = getxys(inputfiles)

    print "%s points read from %s files" % (str(len(S)), str(len(inputfiles)))

    # remove values where sidescan intensity is zero
    ind = np.where(np.logical_not(S==0))[0]

    X = X[ind]; Y = Y[ind]
    S = S[ind]; D = D[ind]
    R = R[ind]; h = h[ind]
    t = t[ind]; i = i[ind]

    del ind   
   
    # save to file for temporary storage
    pickle.dump( S, open( "S.p", "wb" ) ); del S
    pickle.dump( D, open( "D.p", "wb" ) ); del D
    pickle.dump( t, open( "t.p", "wb" ) ); del t
    pickle.dump( i, open( "i.p", "wb" ) ); del i

    pickle.dump( X, open( "X.p", "wb" ) ); del X
    pickle.dump( Y, open( "Y.p", "wb" ) ); del Y
    pickle.dump( R, open( "R.p", "wb" ) ); 
    pickle.dump( h, open( "h.p", "wb" ) ); 

    #grazing angle
    g = np.arctan(R.flatten(),h.flatten())
    pickle.dump( g, open( "g.p", "wb" ) ); del g, R, h
   
    #### prepare grids
    R = pickle.load( open( "R.p", "rb" ) )

    ## actual along-track resolution is this: dx times dy = Af
    tmp = R * dx * (c*0.007 / 2)
    del R

    if res==99:
       resg = np.min(tmp[tmp>0])
       del tmp
    else:
       resg = res

    X = pickle.load( open( "X.p", "rb" ) )
    Y = pickle.load( open( "Y.p", "rb" ) )
    
    humlon, humlat = trans(X, Y, inverse=True)

    grid_x, grid_y = np.meshgrid( np.arange(np.min(X), np.max(X), resg), np.arange(np.min(Y), np.max(Y), resg) )    
 
    shape = np.shape(grid_x)

    tree = KDTree(zip(X.flatten(), Y.flatten()))
    del X, Y

    #k nearest neighbour
    dist, inds = tree.query(zip(grid_x.flatten(), grid_y.flatten()), k = k)
    #del grid_x, grid_y
    g = pickle.load( open( "g.p", "rb" ) )
    w = g[inds] + 1.0 #/ dist**2
    del g

    w[np.isinf(w)]=1
    w[np.isnan(w)]=1
    w[w>10000]=10000
    w[w<=0]=1
    
    # load in sidescan intensity
    S = pickle.load( open( "S.p", "rb" ) )
    # filter out noise pixels
    S[S<noise] = np.nan

    if k==1:
       Sdat_g = (w * S.flatten()[inds]).reshape(shape)
       del w
       dist = dist.reshape(shape)
    else:
       Sdat_g = (np.sum(w * S.flatten()[inds], axis=1) / np.sum(w, axis=1)).reshape(shape)
       del w
       dist = np.mean(dist,axis=1).reshape(shape)

    del S

    Sdat_g[dist>1] = np.nan
    Sdat_g[Sdat_g<noise] = np.nan

    dat = Sdat_g.copy()
    dat[dist>1] = 0
    dat2 = replace_nans.RN(dat.astype('float64'),1000,0.01,2,'localmean').getdata()
    dat2[dat==0] = np.nan
    del dat

    dat2[dat2<noise] = np.nan

    Sdat_g = dat2.copy()
    del dat2
   
    Sdat_g[Sdat_g==0] = np.nan
    Sdat_g[np.isinf(Sdat_g)] = np.nan
    Sdat_gm = np.ma.masked_invalid(Sdat_g)
    del Sdat_g

    glon, glat = trans(grid_x, grid_y, inverse=True)
    del grid_x, grid_y

    try:
       print "drawing and printing map ..."
       fig = plt.figure(frameon=False)
       map = Basemap(projection='merc', epsg=cs2cs_args.split(':')[1], 
        resolution = 'i', #h #f
        llcrnrlon=np.min(humlon)-0.00001, llcrnrlat=np.min(humlat)-0.00001,
        urcrnrlon=np.max(humlon)+0.00001, urcrnrlat=np.max(humlat)+0.00001)

       gx,gy = map.projtran(glon, glat)
       #del glon, glat   

       ax = plt.Axes(fig, [0., 0., 1., 1.], )
       ax.set_axis_off()      
       fig.add_axes(ax)

       if Sdat_gm.size > 25000000:
          print "matrix size > 25,000,000 - decimating by factor of 5 for display"
          map.pcolormesh(gx[::5,::5], gy[::5,::5], Sdat_gm[::5,::5], cmap='gray')
       else:
          map.pcolormesh(gx, gy, Sdat_gm, cmap='gray')
       plt.axis('tight')

       custom_save(sonpath,'map')#+str(p))
       del fig 

    except:
       print "error: map could not be created..."


    kml = simplekml.Kml()
    ground = kml.newgroundoverlay(name='GroundOverlay', altitude=1)
    ground.icon.href = 'map.png'
   
    #ground.gxlatlonquad.coords = [(np.max(humlon)+0.00001,np.max(humlat)-0.00001), (np.max(humlon)+0.00001,np.min(humlat)-0.00001), (np.min(humlon)+0.00001,np.min(humlat)-0.00001), (np.min(humlon)+0.00001,np.max(humlat)-0.00001)]   

    ground.latlonbox.north = np.min(humlat)-0.00001
    ground.latlonbox.south = np.max(humlat)+0.00001
    ground.latlonbox.east =  np.max(humlon)+0.00001
    ground.latlonbox.west =  np.min(humlon)-0.00001
    ground.latlonbox.rotation = 0

    kml.save(os.path.normpath(os.path.join(sonpath,'GroundOverlay.kml')))


    print "drawing and printing map ..."
    fig = plt.figure(frameon=False)
    map = Basemap(projection='merc', epsg=cs2cs_args.split(':')[1], 
     resolution = 'i', #h #f
     llcrnrlon=np.min(humlon)-0.001, llcrnrlat=np.min(humlat)-0.001,
     urcrnrlon=np.max(humlon)+0.001, urcrnrlat=np.max(humlat)+0.001)

    gx,gy = map.projtran(glon, glat)
       
    try:
       map.arcgisimage(server='http://server.arcgisonline.com/ArcGIS', service='ESRI_Imagery_World_2D', xpixels=1000, ypixels=None, dpi=300)
    except:
       map.arcgisimage(server='http://server.arcgisonline.com/ArcGIS', service='World_Imagery', xpixels=1000, ypixels=None, dpi=300)
    #finally:
    #   print "error: map could not be created..."
      
    ax = plt.Axes(fig, [0., 0., 1., 1.], )
    ax.set_axis_off()
    fig.add_axes(ax)

    if dogrid==1:
      if Sdat_gm.size > 25000000:
         print "matrix size > 25,000,000 - decimating by factor of 5 for display"
         map.pcolormesh(gx[::5,::5], gy[::5,::5], Sdat_gm[::5,::5], cmap='gray', vmin=np.nanmin(Sdat_gm), vmax=np.nanmax(Sdat_gm))
      else:
         map.pcolormesh(gx, gy, Sdat_gm, cmap='gray', vmin=np.nanmin(Sdat_gm), vmax=np.nanmax(Sdat_gm))

    custom_save2(sonpath,'map_imagery')
    del fig 

   
    if os.name=='posix': # true if linux/mac
       elapsed = (time.time() - start)
    else: # windows
       elapsed = (time.clock() - start)
    print "Processing took ", elapsed , "seconds to analyse"

    print "Done!"
          
# =========================================================
def getdat(inputfile, filenum):
   tmp = pd.read_csv(inputfile, sep=' ', header=None)
   return np.hstack((tmp, filenum*np.ones((len(tmp),1))))
      
# =========================================================
def getxys(inputfiles):
   o = Parallel(n_jobs = -1, verbose=0)(delayed(getdat)(inputfiles[k], k) for k in xrange(len(inputfiles)))
   #return zip(*o)
   tmp = np.vstack(o)
   return tmp[:,0], tmp[:,1], tmp[:,2], tmp[:,3], tmp[:,4], tmp[:,5], tmp[:,6], tmp[:,7] 
          
# =========================================================
def write_points(e, n, t, d, dat_port, dat_star, data_R, pix_m, res, cs2cs_args, sonpath, p, c, dx):
 
   trans =  pyproj.Proj(init=cs2cs_args)   

   merge = np.vstack((dat_port,dat_star))
   
   merge[np.isnan(merge)] = 0
   merge = merge[:,:len(n)]

   ## actual along-track resolution is this: dx times dy = Af
   tmp = data_R * dx * (c*0.007 / 2) #dx = np.arcsin(c/(1000*meta['t']*meta['f']))
   res_grid = np.vstack((tmp, tmp))
   del tmp 

   res_grid = res_grid[:np.shape(merge)[0],:np.shape(merge)[1]]

   merge = merge - 10*np.log10(res_grid)

   merge[np.isnan(merge)] = 0
   merge[merge<0] = 0

   R = np.vstack((np.flipud(data_R),data_R))
   R = R[:np.shape(merge)[0],:np.shape(merge)[1]]
  
   # get number pixels in scan line
   extent = int(np.shape(merge)[0]/2)

   yvec = np.squeeze(np.linspace(np.squeeze(pix_m),extent*np.squeeze(pix_m),extent))

   X, Y, D, h, t  = getXY(e,n,yvec,np.squeeze(d),t,extent)
   
   D[np.isnan(D)] = 0
   h[np.isnan(h)] = 0
   t[np.isnan(t)] = 0
       
   X = X[np.where(np.logical_not(np.isnan(Y)))]
   merge = merge.flatten()[np.where(np.logical_not(np.isnan(Y)))]
   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isnan(Y)))]
   Y = Y[np.where(np.logical_not(np.isnan(Y)))]
   D = D[np.where(np.logical_not(np.isnan(Y)))]
   R = R.flatten()[np.where(np.logical_not(np.isnan(Y)))]
   h = h[np.where(np.logical_not(np.isnan(Y)))]
   t = t[np.where(np.logical_not(np.isnan(Y)))]   
         
   Y = Y[np.where(np.logical_not(np.isnan(X)))]
   merge = merge.flatten()[np.where(np.logical_not(np.isnan(X)))]
   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isnan(X)))]
   X = X[np.where(np.logical_not(np.isnan(X)))]
   D = D[np.where(np.logical_not(np.isnan(X)))]
   R = R.flatten()[np.where(np.logical_not(np.isnan(X)))]
   h = h[np.where(np.logical_not(np.isnan(X)))]
   t = t[np.where(np.logical_not(np.isnan(X)))]   
         
   X = X[np.where(np.logical_not(np.isnan(merge)))]
   Y = Y[np.where(np.logical_not(np.isnan(merge)))]
   merge = merge[np.where(np.logical_not(np.isnan(merge)))]
   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isnan(merge)))]
   D = D[np.where(np.logical_not(np.isnan(merge)))]
   R = R[np.where(np.logical_not(np.isnan(merge)))]
   h = h[np.where(np.logical_not(np.isnan(merge)))]
   t = t[np.where(np.logical_not(np.isnan(merge)))]   

   X = X[np.where(np.logical_not(np.isinf(merge)))]
   Y = Y[np.where(np.logical_not(np.isinf(merge)))]
   merge = merge[np.where(np.logical_not(np.isinf(merge)))]
   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isinf(merge)))]
   D = D[np.where(np.logical_not(np.isinf(merge)))]
   R = R[np.where(np.logical_not(np.isinf(merge)))]
   h = h[np.where(np.logical_not(np.isinf(merge)))]
   t = t[np.where(np.logical_not(np.isinf(merge)))] 
         
   ## write raw bs to file
   outfile = os.path.normpath(os.path.join(sonpath,'x_y_ss_raw'+str(p)+'.asc'))
   write.txtwrite( outfile, np.hstack((humutils.ascol(X.flatten()),humutils.ascol(Y.flatten()), humutils.ascol(merge.flatten()), humutils.ascol(D.flatten()), humutils.ascol(R.flatten()), humutils.ascol(h.flatten()), humutils.ascol(t.flatten())  )) )
      
   del D, R, h, t, X, Y, merge, res_grid

# =========================================================
def custom_save2(figdirec,root):
    plt.savefig(os.path.normpath(os.path.join(figdirec,root)),bbox_inches='tight',dpi=1000, transparent=False)

# =========================================================
def custom_save(figdirec,root):
    plt.savefig(os.path.normpath(os.path.join(figdirec,root)),bbox_inches='tight',dpi=1000, transparent=True)

# =========================================================
def calc_beam_pos(dist, bearing, x, y):

   dist_x, dist_y = (dist*np.sin(bearing), dist*np.cos(bearing))
   xfinal, yfinal = (x + dist_x, y + dist_y)
   return (xfinal, yfinal)

# =========================================================
def getmesh(minX, maxX, minY, maxY, res):

   complete=0
   while complete==0:
      try:
         grid_x, grid_y = np.meshgrid( np.arange(minX, maxX, res), np.arange(minY, maxY, res) )
         if 'grid_x' in locals(): 
            complete=1 
      except:
         print "memory error: trying grid resolution of %s" % (str(res*2))
         res = res*2
         
   return grid_x, grid_y, res


# =========================================================
def getgrid_lm(humlon, humlat, merge, influence, minX, maxX, minY, maxY, res, mode):

   complete=0
   while complete==0:
      try:
         grid_x, grid_y, res = getmesh(minX, maxX, minY, maxY, res)
         longrid, latgrid = trans(grid_x, grid_y, inverse=True)
         shape = np.shape(grid_x)
         targ_def = pyresample.geometry.SwathDefinition(lons=longrid.flatten(), lats=latgrid.flatten())
         del longrid, latgrid

         orig_def = pyresample.geometry.SwathDefinition(lons=humlon.flatten(), lats=humlat.flatten())

         if mode==1:
            dat = pyresample.kd_tree.resample_nearest(orig_def, merge.flatten(), targ_def, radius_of_influence=influence, fill_value=None, nprocs = cpu_count())
            stdev = None
            counts = None
         elif mode==2:
            dat, stdev, counts = pyresample.kd_tree.resample_custom(orig_def, merge.flatten(),targ_def, radius_of_influence=influence, neighbours=nn, weight_funcs=wf, fill_value=None, with_uncert = True, nprocs = cpu_count())
         else:
            dat, stdev, counts = pyresample.kd_tree.resample_gauss(orig_def, merge.flatten(), targ_def, radius_of_influence=influence, neighbours=nn, sigmas=sigmas, fill_value=None, with_uncert = np.nan, nprocs = cpu_count(), epsilon = eps)
 
         if 'dat' in locals(): 
            complete=1 
      except:
         print "memory error: trying grid resolution of %s" % (str(res*2))
         res = res*2

   return dat, stdev, counts, res, complete, shape


# =========================================================
def getxy(e, n, yvec, d, t,extent):
   x = np.concatenate((np.tile(e,extent) , np.tile(e,extent)))
   rangedist = np.sqrt(np.power(yvec, 2.0) - np.power(d, 2.0))
   y = np.concatenate((n+rangedist, n-rangedist))
   # Rotate line around center point
   xx = e - ((x - e) * np.cos(t)) - ((y - n) * np.sin(t))
   yy = n - ((x - e) * np.sin(t)) + ((y - n) * np.cos(t))
   xx, yy = calc_beam_pos(d, t, xx, yy)
   #x, y, eucl. dist, depth, theta 
   return xx, yy, np.sqrt((xx-e)**2 + (yy-n)**2), np.ones(len(xx))*d, np.ones(len(xx))*t

# =========================================================
def getXY(e,n,yvec,d,t,extent):
   print "getting point cloud ..." 

   o = Parallel(n_jobs = cpu_count(), verbose=0)(delayed(getxy)(e[k], n[k], yvec, d[k], t[k], extent) for k in xrange(len(n)))

   #eating, northing, distance to sonar, depth, heading
   X, Y, D, h, t = zip(*o)

   # merge flatten and stack
   X = np.asarray(X,'float').T
   X = X.flatten()

   # merge flatten and stack
   Y = np.asarray(Y,'float').T
   Y = Y.flatten()

   # merge flatten and stack
   D = np.asarray(D,'float').T
   D = D.flatten()

   # merge flatten and stack
   h = np.asarray(h,'float').T
   h = h.flatten()
   
   # merge flatten and stack
   t = np.asarray(t,'float').T
   t = t.flatten()
         
   return X, Y, D, h, t

# =========================================================
# =========================================================
if __name__ == '__main__':

   map(humfile, sonpath, cs2cs_args, dogrid, res, dowrite, mode, nn, influence, numstdevs)

   #kml.save(sonpath+'GroundOverlay'+str(p)+'.kml')
   
   #y = np.concatenate((n[k]+yvec, n[k]-yvec))
   
   #merge = np.vstack((np.flipud(port_fp[p]),star_fp[p]))      
      #mask = binary_fill_holes(mask, structure=np.ones((15,15)))
      #mask = ~binary_fill_holes(~mask, structure=np.ones((15,15)))


      ### mask
      #if np.floor(np.sqrt(1/res))-1 > 0.0:
      #   dat[dist> np.floor(np.sqrt(1/res))-1 ] = np.nan #np.floor(np.sqrt(1/res))-1 ] = np.nan
      #else:
      #   dat[dist> np.sqrt(1/res) ] = np.nan #np.floor(np.sqrt(1/res))-1 ] = np.nan

      #del dist, tree


    ## for debugging/testing
    #p=2
#    e = esi[shape_port[-1]*p:shape_port[-1]*(p+1)]
#    n = nsi[shape_port[-1]*p:shape_port[-1]*(p+1)]
#    t = theta[shape_port[-1]*p:shape_port[-1]*(p+1)]
#    d = dist_tvg[shape_port[-1]*p:shape_port[-1]*(p+1)]
#    dat_port = port_fp[p]
#    dat_star = star_fp[p]
#    data_R = R_fp[p]
#    dx = np.arcsin(meta['c']/(1000*meta['t']*meta['f']))
#    pix_m = meta['pix_m']
#    c = meta['c']

#    if len(shape_star)>2:    
#       for p in xrange(len(star_fp)):
#          res = make_map(esi[shape_port[-1]*p:shape_port[-1]*(p+1)], nsi[shape_port[-1]*p:shape_port[-1]*(p+1)], theta[shape_port[-1]*p:shape_port[-1]*(p+1)], dist_tvg[shape_port[-1]*p:shape_port[-1]*(p+1)], port_fp[p], star_fp[p], R_fp[p], meta['pix_m'], res, cs2cs_args, sonpath, p, dogrid, dowrite, mode, nn, influence, numstdevs, meta['c'], np.arcsin(meta['c']/(1000*meta['t']*meta['f'])))
#          print "grid resolution is %s" % (str(res))
#    else:
#       res = make_map(esi, nsi, theta, dist_tvg, port_fp, star_fp, R_fp, meta['pix_m'], res, cs2cs_args, sonpath, 0, dogrid, dowrite, mode, nn, influence, numstdevs, meta['c'], np.arcsin(meta['c']/(1000*meta['t']*meta['f'])))

#    if os.name=='posix': # true if linux/mac
#       elapsed = (time.time() - start)
#    else: # windows
#       elapsed = (time.clock() - start)
#    print "Processing took ", elapsed , "seconds to analyse"

#    print "Done!"


## =========================================================
#def make_map(e, n, t, d, dat_port, dat_star, data_R, pix_m, res, cs2cs_args, sonpath, p, dogrid, dowrite, mode, nn, influence, numstdevs, c, dx):
#   
#   trans =  pyproj.Proj(init=cs2cs_args)   

#   merge = np.vstack((dat_port,dat_star))
#   
#   merge[np.isnan(merge)] = 0
#   merge = merge[:,:len(n)]

#   ## actual along-track resolution is this: dx times dy = Af
#   tmp = data_R * dx * (c*0.007 / 2) #dx = np.arcsin(c/(1000*meta['t']*meta['f']))
#   res_grid = np.vstack((tmp, tmp))
#   del tmp 

#   res_grid = res_grid[:np.shape(merge)[0],:np.shape(merge)[1]]

#   merge = merge - 10*np.log10(res_grid)

#   merge[np.isnan(merge)] = 0
#   merge[merge<0] = 0

#   R = np.vstack((np.flipud(data_R),data_R))
#   R = R[:np.shape(merge)[0],:np.shape(merge)[1]]
#  
#   # get number pixels in scan line
#   extent = int(np.shape(merge)[0]/2)

#   yvec = np.squeeze(np.linspace(np.squeeze(pix_m),extent*np.squeeze(pix_m),extent))

#   X, Y, D, h, t  = getXY(e,n,yvec,np.squeeze(d),t,extent)
#   
#   D[np.isnan(D)] = 0
#   h[np.isnan(h)] = 0
#   t[np.isnan(t)] = 0
#       
#   X = X[np.where(np.logical_not(np.isnan(Y)))]
#   merge = merge.flatten()[np.where(np.logical_not(np.isnan(Y)))]
#   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isnan(Y)))]
#   Y = Y[np.where(np.logical_not(np.isnan(Y)))]
#   D = D[np.where(np.logical_not(np.isnan(Y)))]
#   R = R.flatten()[np.where(np.logical_not(np.isnan(Y)))]
#   h = h[np.where(np.logical_not(np.isnan(Y)))]
#   t = t[np.where(np.logical_not(np.isnan(Y)))]   
#         
#   Y = Y[np.where(np.logical_not(np.isnan(X)))]
#   merge = merge.flatten()[np.where(np.logical_not(np.isnan(X)))]
#   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isnan(X)))]
#   X = X[np.where(np.logical_not(np.isnan(X)))]
#   D = D[np.where(np.logical_not(np.isnan(X)))]
#   R = R.flatten()[np.where(np.logical_not(np.isnan(X)))]
#   h = h[np.where(np.logical_not(np.isnan(X)))]
#   t = t[np.where(np.logical_not(np.isnan(X)))]   
#         
#   X = X[np.where(np.logical_not(np.isnan(merge)))]
#   Y = Y[np.where(np.logical_not(np.isnan(merge)))]
#   merge = merge[np.where(np.logical_not(np.isnan(merge)))]
#   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isnan(merge)))]
#   D = D[np.where(np.logical_not(np.isnan(merge)))]
#   R = R[np.where(np.logical_not(np.isnan(merge)))]
#   h = h[np.where(np.logical_not(np.isnan(merge)))]
#   t = t[np.where(np.logical_not(np.isnan(merge)))]   

#   X = X[np.where(np.logical_not(np.isinf(merge)))]
#   Y = Y[np.where(np.logical_not(np.isinf(merge)))]
#   merge = merge[np.where(np.logical_not(np.isinf(merge)))]
#   res_grid = res_grid.flatten()[np.where(np.logical_not(np.isinf(merge)))]
#   D = D[np.where(np.logical_not(np.isinf(merge)))]
#   R = R[np.where(np.logical_not(np.isinf(merge)))]
#   h = h[np.where(np.logical_not(np.isinf(merge)))]
#   t = t[np.where(np.logical_not(np.isinf(merge)))] 
#         
#   if dowrite==1:
#      ## write raw bs to file
#      outfile = os.path.normpath(os.path.join(sonpath,'x_y_ss_raw'+str(p)+'.asc'))
#      write.txtwrite( outfile, np.hstack((humutils.ascol(X.flatten()),humutils.ascol(Y.flatten()), humutils.ascol(merge.flatten()), humutils.ascol(D.flatten()), humutils.ascol(R.flatten()), humutils.ascol(h.flatten()), humutils.ascol(t.flatten())  )) )
#      
#   del D, R, h, t
#  
#   humlon, humlat = trans(X, Y, inverse=True)

#   if dogrid==1:

#      if res==99:
#         resg = np.min(res_grid[res_grid>0])
#      else:
#         resg = res

#      complete=0
#      while complete==0:
#         try:
#            grid_x, grid_y, res = getmesh(np.min(X), np.max(X), np.min(Y), np.max(Y), resg)
#            longrid, latgrid = trans(grid_x, grid_y, inverse=True)
#            shape = np.shape(grid_x)

#            ## create mask for where the data is not
#            tree = KDTree(np.c_[X.flatten(),Y.flatten()])
#            try:
#               dist, _ = tree.query(np.c_[grid_x.ravel(), grid_y.ravel()], k=1, n_jobs=cpu_count())
#            except:
#               print ".... update your scipy installation to use faster kd-tree queries"
#               dist, _ = tree.query(np.c_[grid_x.ravel(), grid_y.ravel()], k=1)

#            dist = dist.reshape(grid_x.shape)
#      
#            targ_def = pyresample.geometry.SwathDefinition(lons=longrid.flatten(), lats=latgrid.flatten())
#            del longrid, latgrid

#            orig_def = pyresample.geometry.SwathDefinition(lons=humlon.flatten(), lats=humlat.flatten())
#            if 'orig_def' in locals(): 
#               complete=1 
#         except:
#            print "memory error: trying grid resolution of %s" % (str(resg*2))
#            resg = resg*2

#      if mode==1:

#         complete=0
#         while complete==0:
#            try:
#               dat = pyresample.kd_tree.resample_nearest(orig_def, merge.flatten(), targ_def, radius_of_influence=influence, fill_value=None, nprocs = cpu_count()) 

#               r_dat = pyresample.kd_tree.resample_nearest(orig_def, res_grid.flatten(), targ_def, radius_of_influence=influence, fill_value=None, nprocs = cpu_count()) 

#               stdev = None
#               counts = None
#               if 'dat' in locals(): 
#                  complete=1 
#            except:
#               del grid_x, grid_y, targ_def, orig_def
#               dat, stdev, counts, resg, complete, shape = getgrid_lm(humlon, humlat, merge, influence, min(X), max(X), min(Y), max(Y), resg*2, mode)         
#               r_dat, stdev, counts, resg, complete, shape = getgrid_lm(humlon, humlat, res_grid, influence, min(X), max(X), min(Y), max(Y), resg*2, mode)   

#      elif mode==2:

#         # custom inverse distance 
#         wf = lambda r: 1/r**2

#         complete=0
#         while complete==0:
#            try:
#               dat, stdev, counts = pyresample.kd_tree.resample_custom(orig_def, merge.flatten(),targ_def, radius_of_influence=influence, neighbours=nn, weight_funcs=wf, fill_value=None, with_uncert = True, nprocs = cpu_count())

#               r_dat = pyresample.kd_tree.resample_custom(orig_def, res_grid.flatten(), targ_def, radius_of_influence=influence, neighbours=nn, weight_funcs=wf, fill_value=None, with_uncert = False, nprocs = cpu_count())

#               if 'dat' in locals(): 
#                  complete=1 
#            except:
#               del grid_x, grid_y, targ_def, orig_def
#               dat, stdev, counts, resg, complete, shape = getgrid_lm(humlon, humlat, merge, influence, min(X), max(X), min(Y), max(Y), resg*2, mode)
#               r_dat, stdev, counts, resg, complete, shape = getgrid_lm(humlon, humlat, res_grid, influence, min(X), max(X), min(Y), max(Y), resg*2, mode)
#               del stdev_null, counts_null

#      elif mode==3:
#         sigmas = 0.1 #m
#         eps = 2

#         complete=0
#         while complete==0:
#            try:
#               dat, stdev, counts = pyresample.kd_tree.resample_gauss(orig_def, merge.flatten(), targ_def, radius_of_influence=influence, neighbours=nn, sigmas=sigmas, fill_value=None, with_uncert = True, nprocs = cpu_count(), epsilon = eps)

#               r_dat = pyresample.kd_tree.resample_gauss(orig_def, res_grid.flatten(), targ_def, radius_of_influence=influence, neighbours=nn, sigmas=sigmas, fill_value=None, with_uncert = False, nprocs = cpu_count(), epsilon = eps)

#               if 'dat' in locals(): 
#                  complete=1 
#            except:
#               del grid_x, grid_y, targ_def, orig_def
#               dat, stdev, counts, resg, complete, shape = getgrid_lm(humlon, humlat, merge, influence, min(X), max(X), min(Y), max(Y), resg*2, mode)
#               r_dat, stdev_null, counts_null, resg, complete, shape = getgrid_lm(humlon, humlat, res_grid, influence, min(X), max(X), min(Y), max(Y), resg*2, mode)
#               del stdev_null, counts_null

#      del X, Y

#      dat = dat.reshape(shape)

#      dat[dist>res*5] = np.nan
#      del dist

#      r_dat = r_dat.reshape(shape)
#      dat = dat*np.sqrt(np.cos(np.deg2rad(r_dat))) #dat*np.sqrt(r_dat) + dat
#      del r_dat

#      if mode>1:
#         stdev = stdev.reshape(shape)
#         counts = counts.reshape(shape)

#      mask = dat.mask.copy()

#      dat[mask==1] = np.nan
#      #dat[mask==1] = 0

#      if mode>1:
#         dat[(stdev>numstdevs) & (mask!=0)] = np.nan
#         dat[(counts<nn) & (counts>0)] = np.nan

#      #dat2 = replace_nans.RN(dat.astype('float64'),1000,0.01,2,'localmean').getdata()
#      #dat2[dat==0] = np.nan

#      # get a new mask
#      #mask = np.isnan(dat2)

#      #mask = ~binary_dilation(binary_erosion(~mask,structure=np.ones((15,15))), structure=np.ones((15,15)))
#      
#      #dat2[mask==1] = np.nan
#      #dat2[dat2<1] = np.nan

#      #del dat
#      #dat = dat2
#      #del dat2


#   if dogrid==1:

#      dat[dat==0] = np.nan
#      dat[np.isinf(dat)] = np.nan
#      datm = np.ma.masked_invalid(dat)

#      glon, glat = trans(grid_x, grid_y, inverse=True)
#      del grid_x, grid_y

#   try:
#      print "drawing and printing map ..."
#      fig = plt.figure(frameon=False)
#      map = Basemap(projection='merc', epsg=cs2cs_args.split(':')[1], 
#       resolution = 'i', #h #f
#       llcrnrlon=np.min(humlon)-0.00001, llcrnrlat=np.min(humlat)-0.00001,
#       urcrnrlon=np.max(humlon)+0.00001, urcrnrlat=np.max(humlat)+0.00001)

#      if dogrid==1:
#         gx,gy = map.projtran(glon, glat)

#      ax = plt.Axes(fig, [0., 0., 1., 1.], )
#      ax.set_axis_off()
#      fig.add_axes(ax)

#      if dogrid==1:
#         if datm.size > 25000000:
#            print "matrix size > 25,000,000 - decimating by factor of 5 for display"
#            map.pcolormesh(gx[::5,::5], gy[::5,::5], datm[::5,::5], cmap='gray')#, vmin=np.nanmin(datm), vmax=np.nanmax(datm))
#         else:
#            map.pcolormesh(gx, gy, datm, cmap='gray')#@, vmin=np.nanmin(datm), vmax=np.nanmax(datm))
#         #del datm, dat
#      else: 
#         ## draw point cloud
#         x,y = map.projtran(humlon, humlat)
#         map.scatter(x.flatten(), y.flatten(), 0.5, merge.flatten(), cmap='gray', linewidth = '0')

#      custom_save(sonpath,'map'+str(p))
#      del fig 

#   except:
#      print "error: map could not be created..."

#   kml = simplekml.Kml()
#   ground = kml.newgroundoverlay(name='GroundOverlay', altitude=1)
#   ground.icon.href = 'map'+str(p)+'.png'
#   
#   #ground.gxlatlonquad.coords = [(np.max(humlon)+0.00001,np.max(humlat)-0.00001), (np.max(humlon)+0.00001,np.min(humlat)-0.00001), (np.min(humlon)+0.00001,np.min(humlat)-0.00001), (np.min(humlon)+0.00001,np.max(humlat)-0.00001)]   

#   ground.latlonbox.north = np.min(humlat)-0.00001
#   ground.latlonbox.south = np.max(humlat)+0.00001
#   ground.latlonbox.east =  np.max(humlon)+0.00001
#   ground.latlonbox.west =  np.min(humlon)-0.00001
#   ground.latlonbox.rotation = 0

#   kml.save(os.path.normpath(os.path.join(sonpath,'GroundOverlay'+str(p)+'.kml')))

#   print "drawing and printing map ..."
#   fig = plt.figure(frameon=False)
#   map = Basemap(projection='merc', epsg=cs2cs_args.split(':')[1], 
#    resolution = 'i', #h #f
#    llcrnrlon=np.min(humlon)-0.001, llcrnrlat=np.min(humlat)-0.001,
#    urcrnrlon=np.max(humlon)+0.001, urcrnrlat=np.max(humlat)+0.001)

#   try:
#      map.arcgisimage(server='http://server.arcgisonline.com/ArcGIS', service='ESRI_Imagery_World_2D', xpixels=1000, ypixels=None, dpi=300)
#   except:
#      map.arcgisimage(server='http://server.arcgisonline.com/ArcGIS', service='World_Imagery', xpixels=1000, ypixels=None, dpi=300)
#   #finally:
#   #   print "error: map could not be created..."
#      
#   if dogrid==1:
#      gx,gy = map.projtran(glon, glat)

#   ax = plt.Axes(fig, [0., 0., 1., 1.], )
#   ax.set_axis_off()
#   fig.add_axes(ax)

#   if dogrid==1:
#      if datm.size > 25000000:
#         print "matrix size > 25,000,000 - decimating by factor of 5 for display"
#         map.pcolormesh(gx[::5,::5], gy[::5,::5], datm[::5,::5], cmap='gray', vmin=np.nanmin(datm), vmax=np.nanmax(datm))
#      else:
#         map.pcolormesh(gx, gy, datm, cmap='gray', vmin=np.nanmin(datm), vmax=np.nanmax(datm))
#      del datm, dat
#   else: 
#      ## draw point cloud
#      x,y = map.projtran(humlon, humlat)
#      map.scatter(x.flatten(), y.flatten(), 0.5, merge.flatten(), cmap='gray', linewidth = '0')

#   custom_save2(sonpath,'map_imagery'+str(p))
#   del fig 


#   del humlat, humlon
#   return res #return the new resolution      