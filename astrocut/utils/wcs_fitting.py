#################################################################################
#
# Licensed under a 3-clause BSD style license
#           - see https://github.com/astropy/astropy/blob/master/LICENSE.rst
#
# wcs fitting functionality
#          by Clare Shanahan (shannnnnyyy @github)
#
# Will be added to Astropy (PR: https://github.com/astropy/astropy/pull/7884)
#
# Astropy version is used preferenetially, this is supplied prior to the
# addition of this code to Astropy, and for users using older versions of Astropy
#
#################################################################################

# flake8: noqa

import numpy as np

from astropy import units as u
from astropy.wcs.utils import celestial_frame_to_wcs

def _linear_wcs_fit(params, lon, lat, x, y, w_obj):  # pragma: no cover
    """
    Objective function for fitting linear terms.

    Parameters
    ----------
    params : array
        6 element array. First 4 elements are PC matrix, last 2 are CRPIX.
    lon, lat: array
        Sky coordinates.
    x, y: array
        Pixel coordinates
    w_obj: `~astropy.wcs.WCS`
        WCS object
        """
    cd = params[0:4]
    crpix = params[4:6]

    w_obj.wcs.cd = ((cd[0], cd[1]), (cd[2], cd[3]))
    w_obj.wcs.crpix = crpix
    lon2, lat2 = w_obj.wcs_pix2world(x, y, 0)

    resids = np.concatenate((lon-lon2, lat-lat2))
    resids[resids > 180] = 360 - resids[resids > 180]
    resids[resids < -180] = 360	+ resids[resids < -180]

    return resids


def _sip_fit(params, lon, lat, u, v, w_obj, order, coeff_names):  # pragma: no cover

    """ Objective function for fitting SIP.
     Parameters
    -----------
    params : array
        Fittable parameters. First 4 elements are PC matrix, last 2 are CRPIX.
    lon, lat: array
        Sky coordinates.
    u, v: array
        Pixel coordinates
    w_obj: `~astropy.wcs.WCS`
        WCS object
    """

    from astropy.modeling.models import SIP, InverseSIP   # here to avoid circular import

    # unpack params
    crpix = params[0:2]
    cdx = params[2:6].reshape((2, 2))
    a_params = params[6:6+len(coeff_names)]
    b_params = params[6+len(coeff_names):]

    # assign to wcs, used for transfomations in this function
    w_obj.wcs.cd = cdx
    w_obj.wcs.crpix = crpix

    a_coeff, b_coeff = {}, {}
    for i in range(len(coeff_names)):
        a_coeff['A_' + coeff_names[i]] = a_params[i]
        b_coeff['B_' + coeff_names[i]] = b_params[i]

    sip = SIP(crpix=crpix, a_order=order, b_order=order,
              a_coeff=a_coeff, b_coeff=b_coeff)
    fuv, guv = sip(u, v)

    xo, yo = np.dot(cdx, np.array([u+fuv-crpix[0], v+guv-crpix[1]]))

    # use all pix2world in case `projection` contains distortion table
    x, y = w_obj.all_world2pix(lon, lat, 0)
    x, y = np.dot(w_obj.wcs.cd, (x-w_obj.wcs.crpix[0], y-w_obj.wcs.crpix[1]))

    resids = np.concatenate((x-xo, y-yo))
    # to avoid bad restuls if near 360 -> 0 degree crossover
    resids[resids > 180] = 360 - resids[resids > 180]
    resids[resids < -180] = 360 + resids[resids < -180]

    return resids



def fit_wcs_from_points(xy, world_coords, proj_point='center',
                        projection='TAN', sip_degree=None):  # pragma: no cover
    """
    Given two matching sets of coordinates on detector and sky,
    compute the WCS.

    Fits a WCS object to matched set of input detector and sky coordinates.
    Optionally, a SIP can be fit to account for geometric
    distortion. Returns an `~astropy.wcs.WCS` object with the best fit
    parameters for mapping between input pixel and sky coordinates.

    The projection type (default 'TAN') can passed in as a string, one of
    the valid three-letter projection codes - or as a WCS object with
    projection keywords already set. Note that if an input WCS has any
    non-polynomial distortion, this will be applied and reflected in the
    fit terms and coefficients. Passing in a WCS object in this way essentially
    allows it to be refit based on the matched input coordinates and projection
    point, but take care when using this option as non-projection related
    keywords in the input might cause unexpected behavior.

    Notes
    ------
    - The fiducial point for the spherical projection can be set to 'center'
      to use the mean position of input sky coordinates, or as an
      `~astropy.coordinates.SkyCoord` object.
    - Units in all output WCS objects will always be in degrees.
    - If the coordinate frame differs between `~astropy.coordinates.SkyCoord`
      objects passed in for ``world_coords`` and ``proj_point``, the frame for
      ``world_coords``  will override as the frame for the output WCS.
    - If a WCS object is passed in to ``projection`` the CD/PC matrix will
      be used as an initial guess for the fit. If this is known to be
      significantly off and may throw off the fit, set to the identity matrix
      (for example, by doing wcs.wcs.pc = [(1., 0.,), (0., 1.)])

    Parameters
    ----------
    xy : tuple of two `numpy.ndarray`
        x & y pixel coordinates.
    world_coords : `~astropy.coordinates.SkyCoord`
        Skycoord object with world coordinates.
    proj_point : 'center' or ~astropy.coordinates.SkyCoord`
        Defaults to 'center', in which the geometric center of input world
        coordinates will be used as the projection point. To specify an exact
        point for the projection, a Skycoord object with a coordinate pair can
        be passed in. For consistency, the units and frame of these coordinates
        will be transformed to match ``world_coords`` if they don't.
    projection : str or `~astropy.wcs.WCS`
        Three letter projection code, of any of standard projections defined
        in the FITS WCS standard. Optionally, a WCS object with projection
        keywords set may be passed in.
    sip_degree : None or int
        If set to a non-zero integer value, will fit SIP of degree
        ``sip_degree`` to model geometric distortion. Defaults to None, meaning
        no distortion corrections will be fit.

    Returns
    -------
    wcs : `~astropy.wcs.WCS`
        The best-fit WCS to the points given.
    """

    from astropy.coordinates import SkyCoord # here to avoid circular import
    import astropy.units as u
    from astropy.wcs import Sip
    from scipy.optimize import least_squares

    xp, yp = xy
    try:
        lon, lat = world_coords.data.lon.deg, world_coords.data.lat.deg
    except AttributeError:
        unit_sph =  world_coords.unit_spherical
        lon, lat = unit_sph.lon.deg, unit_sph.lat.deg

    # verify input
    if (proj_point != 'center') and (type(proj_point) != type(world_coords)):
        raise ValueError("proj_point must be set to 'center', or an" +
                         "`~astropy.coordinates.SkyCoord` object with " +
                         "a pair of points.")
    if proj_point != 'center':
        assert proj_point.size == 1

    proj_codes = [
        'AZP', 'SZP', 'TAN', 'STG', 'SIN', 'ARC', 'ZEA', 'AIR', 'CYP',
        'CEA', 'CAR', 'MER', 'SFL', 'PAR', 'MOL', 'AIT', 'COP', 'COE',
        'COD', 'COO', 'BON', 'PCO', 'TSC', 'CSC', 'QSC', 'HPX', 'XPH'
    ]
    if type(projection) == str:
        if projection not in proj_codes:
            raise ValueError("Must specify valid projection code from list of "
                             + "supported types: ", ', '.join(proj_codes))
        # empty wcs to fill in with fit values
        wcs = celestial_frame_to_wcs(frame=world_coords.frame,
                                     projection=projection)
    else: #if projection is not string, should be wcs object. use as template.
        wcs = copy.deepcopy(projection)
        wcs.cdelt = (1., 1.) # make sure cdelt is 1
        wcs.sip = None

    # Change PC to CD, since cdelt will be set to 1
    if wcs.wcs.has_pc():
        wcs.wcs.cd = wcs.wcs.pc
        wcs.wcs.__delattr__('pc')

    if (type(sip_degree) != type(None)) and (type(sip_degree) != int):
        raise ValueError("sip_degree must be None, or integer.")

    # set pixel_shape to span of input points
    wcs.pixel_shape = (xp.max()+1-xp.min(), yp.max()+1-yp.min())

    # determine CRVAL from input
    close = lambda l, p: p[np.argmin(np.abs(l))]
    if str(proj_point) == 'center':  # use center of input points
        sc1 = SkyCoord(lon.min()*u.deg, lat.max()*u.deg)
        sc2 = SkyCoord(lon.max()*u.deg, lat.min()*u.deg)
        pa = sc1.position_angle(sc2)
        sep = sc1.separation(sc2)
        midpoint_sc = sc1.directional_offset_by(pa, sep/2)
        wcs.wcs.crval = ((midpoint_sc.data.lon.deg, midpoint_sc.data.lat.deg))
        wcs.wcs.crpix = ((xp.max()+xp.min())/2., (yp.max()+yp.min())/2.)
    elif proj_point is not None:  # convert units, initial guess for crpix
        proj_point.transform_to(world_coords)
        wcs.wcs.crval = (proj_point.data.lon.deg, proj_point.data.lat.deg)
        wcs.wcs.crpix = (close(lon-wcs.wcs.crval[0], xp),
                         close(lon-wcs.wcs.crval[1], yp))

    # fit linear terms, assign to wcs
    # use (1, 0, 0, 1) as initial guess, in case input wcs was passed in
    # and cd terms are way off.
    p0 = np.concatenate([wcs.wcs.cd.flatten(), wcs.wcs.crpix.flatten()])
    
    xpmin, xpmax, ypmin, ypmax = xp.min(), xp.max(), yp.min(), yp.max()
    if xpmin==xpmax: xpmin, xpmax = xpmin-0.5, xpmax+0.5
    if ypmin==ypmax: ypmin, ypmax = ypmin-0.5, ypmax+0.5
    
    fit = least_squares(_linear_wcs_fit, p0,
                        args=(lon, lat, xp, yp, wcs),
                        bounds=[[-np.inf,-np.inf,-np.inf,-np.inf, xpmin, ypmin],
                                [ np.inf, np.inf, np.inf, np.inf, xpmax, ypmax]])
    wcs.wcs.crpix = np.array(fit.x[4:6])
    wcs.wcs.cd = np.array(fit.x[0:4].reshape((2, 2)))

    # fit SIP, if specified. Only fit forward coefficients
    if sip_degree:
        degree = sip_degree
        if '-SIP' not in wcs.wcs.ctype[0]:
            wcs.wcs.ctype = [x + '-SIP' for x in wcs.wcs.ctype]

        coef_names = ['{0}_{1}'.format(i, j) for i in range(degree+1)
                      for j in range(degree+1) if (i+j) < (degree+1) and
                      (i+j) > 1]
        p0 = np.concatenate((np.array(wcs.wcs.crpix), wcs.wcs.cd.flatten(),
                             np.zeros(2*len(coef_names))))

        fit = least_squares(_sip_fit, p0,
                            args=(lon, lat, xp, yp, wcs, degree, coef_names))
        coef_fit = (list(fit.x[6:6+len(coef_names)]),
                    list(fit.x[6+len(coef_names):]))

        # put fit values in wcs
        wcs.wcs.cd = fit.x[2:6].reshape((2, 2))
        wcs.wcs.crpix = fit.x[0:2]

        a_vals = np.zeros((degree+1, degree+1))
        b_vals = np.zeros((degree+1, degree+1))

        for coef_name in coef_names:
            a_vals[int(coef_name[0])][int(coef_name[2])] = coef_fit[0].pop(0)
            b_vals[int(coef_name[0])][int(coef_name[2])] = coef_fit[1].pop(0)

        wcs.sip = Sip(a_vals, b_vals, np.zeros((degree+1, degree+1)),
                      np.zeros((degree+1, degree+1)), wcs.wcs.crpix)

    return wcs
