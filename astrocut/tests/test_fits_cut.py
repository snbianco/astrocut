import numpy as np

from astropy.io import fits
from astropy import wcs
from astropy.coordinates import SkyCoord
import astropy.units as u

from .utils_for_test import create_test_imgs
from .. import cutouts


def test_get_cutout_limits():

    test_img_wcs_kwds = fits.Header(cards=[('NAXIS', 2, 'number of array dimensions'),
                                           ('NAXIS1', 20, ''),
                                           ('NAXIS2', 30, ''),
                                           ('CTYPE1', 'RA---TAN', 'Right ascension, gnomonic projection'),
                                           ('CTYPE2', 'DEC--TAN', 'Declination, gnomonic projection'),
                                           ('CRVAL1', 100, '[deg] Coordinate value at reference point'),
                                           ('CRVAL2', 20, '[deg] Coordinate value at reference point'),
                                           ('CRPIX1', 10, 'Pixel coordinate of reference point'),
                                           ('CRPIX2', 15, 'Pixel coordinate of reference point'),
                                           ('CDELT1', 1.0, '[deg] Coordinate increment at reference point'),
                                           ('CDELT2', 1.0, '[deg] Coordinate increment at reference point'),
                                           ('WCSAXES', 2, 'Number of coordinate axes'),
                                           ('PC1_1', 1, 'Coordinate transformation matrix element'),
                                           ('PC2_2', 1, 'Coordinate transformation matrix element'),
                                           ('CUNIT1', 'deg', 'Units of coordinate increment and value'),
                                           ('CUNIT2', 'deg', 'Units of coordinate increment and value')])
    
    test_img_wcs = wcs.WCS(test_img_wcs_kwds)

    center_coord = SkyCoord("100 20", unit='deg')
    cutout_size = [10, 10]

    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    assert (lims[0, 1] - lims[0, 0]) == (lims[1, 1] - lims[1, 0])
    assert (lims == np.array([[ 4, 14], [ 9, 19]])).all()

    cutout_size = [10, 5]
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    assert (lims[0, 1] - lims[0, 0]) == 10
    assert (lims[1, 1] - lims[1, 0]) == 5

    cutout_size = [.1, .1]*u.deg
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    assert (lims[0, 1] - lims[0, 0]) == (lims[1, 1] - lims[1, 0])
    assert (lims[0, 1] - lims[0, 0]) == 1

    cutout_size = [4, 5]*u.deg
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    assert (lims[0, 1] - lims[0, 0]) == 4
    assert (lims[1, 1] - lims[1, 0]) == 5

    center_coord = SkyCoord("90 20", unit='deg')
    cutout_size = [4, 5]*u.deg
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    assert lims[0, 0] < 0

    center_coord = SkyCoord("100 5", unit='deg')
    cutout_size = [4, 5]*u.pixel
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    assert lims[1, 0] < 0


def test_get_cutout_wcs():
    test_img_wcs_kwds = fits.Header(cards=[('NAXIS', 2, 'number of array dimensions'),
                                           ('NAXIS1', 20, ''),
                                           ('NAXIS2', 30, ''),
                                           ('CTYPE1', 'RA---TAN', 'Right ascension, gnomonic projection'),
                                           ('CTYPE2', 'DEC--TAN', 'Declination, gnomonic projection'),
                                           ('CRVAL1', 100, '[deg] Coordinate value at reference point'),
                                           ('CRVAL2', 20, '[deg] Coordinate value at reference point'),
                                           ('CRPIX1', 10, 'Pixel coordinate of reference point'),
                                           ('CRPIX2', 15, 'Pixel coordinate of reference point'),
                                           ('CDELT1', 1.0, '[deg] Coordinate increment at reference point'),
                                           ('CDELT2', 1.0, '[deg] Coordinate increment at reference point'),
                                           ('WCSAXES', 2, 'Number of coordinate axes'),
                                           ('PC1_1', 1, 'Coordinate transformation matrix element'),
                                           ('PC2_2', 1, 'Coordinate transformation matrix element'),
                                           ('CUNIT1', 'deg', 'Units of coordinate increment and value'),
                                           ('CUNIT2', 'deg', 'Units of coordinate increment and value')])
    
    test_img_wcs = wcs.WCS(test_img_wcs_kwds)

    center_coord = SkyCoord("100 20", unit='deg')
    cutout_size = [4, 5]*u.deg
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    cutout_wcs = cutouts._get_cutout_wcs(test_img_wcs, lims)
    assert (cutout_wcs.wcs.crval == [100, 20]).all()
    assert (cutout_wcs.wcs.crpix == [3, 4]).all()

    center_coord = SkyCoord("100 5", unit='deg')
    cutout_size = [4, 5]*u.deg
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    cutout_wcs = cutouts._get_cutout_wcs(test_img_wcs, lims)
    assert (cutout_wcs.wcs.crval == [100, 20]).all()
    assert (cutout_wcs.wcs.crpix == [3, 19]).all()

    center_coord = SkyCoord("110 20", unit='deg')
    cutout_size = [10, 10]*u.deg
    lims = cutouts._get_cutout_limits(test_img_wcs, center_coord, cutout_size)
    cutout_wcs = cutouts._get_cutout_wcs(test_img_wcs, lims)
    assert (cutout_wcs.wcs.crval == [100, 20]).all()
    assert (cutout_wcs.wcs.crpix == [-3, 6]).all() 

    
def test_fits_cut(tmpdir):

    test_images = create_test_imgs(50, 6)

    # Single file
    center_coord = SkyCoord("150.1163213 2.200973097", unit='deg')
    cutout_size = 10
    cutout_file = cutouts.fits_cut(test_images, center_coord, cutout_size, single_outfile=True)
    assert isinstance(cutout_file, str)
    
    cutout_hdulist = fits.open(cutout_file)
    assert len(cutout_hdulist) == len(test_images) + 1  # num imgs + primary header

    cut1 = cutout_hdulist[1].data
    assert cut1.shape == (cutout_size,cutout_size)
    assert cutout_hdulist[1].data.shape == cutout_hdulist[2].data.shape
    assert cutout_hdulist[2].data.shape == cutout_hdulist[3].data.shape
    assert cutout_hdulist[3].data.shape == cutout_hdulist[4].data.shape
    assert cutout_hdulist[4].data.shape == cutout_hdulist[5].data.shape
    assert cutout_hdulist[5].data.shape == cutout_hdulist[6].data.shape
    
    cut_wcs = wcs.WCS(cutout_hdulist[1].header)
    sra, sdec = cut_wcs.all_pix2world(cutout_size/2, cutout_size/2, 0)
    assert round(float(sra), 4) == round(center_coord.ra.deg, 4)
    assert round(float(sdec), 4) == round(center_coord.dec.deg, 4)

    cutout_hdulist.close()

    # Multiple files
    cutout_files = cutouts.fits_cut(test_images, center_coord, cutout_size,
                                    drop_after="Dummy1", single_outfile=False)

    assert isinstance(cutout_files, list)
    assert len(cutout_files) == len(test_images)

    cutout_hdulist = fits.open(cutout_files[0])
    assert len(cutout_hdulist) == 1
    
    cut1 = cutout_hdulist[0].data
    assert cut1.shape == (cutout_size, cutout_size)
    
    cut_wcs = wcs.WCS(cutout_hdulist[0].header)
    sra,sdec = cut_wcs.all_pix2world(cutout_size/2, cutout_size/2,0)
    assert round(float(sra), 4) == round(center_coord.ra.deg, 4)
    assert round(float(sdec), 4) == round(center_coord.dec.deg, 4)

    cutout_hdulist.close()

    # Do an off the edge test
    center_coord = SkyCoord("150.1163213 2.2005731", unit='deg')
    cutout_file = cutouts.fits_cut(test_images, center_coord, cutout_size, single_outfile=True)
    assert isinstance(cutout_file, str)
    
    cutout_hdulist = fits.open(cutout_file)
    assert len(cutout_hdulist) == len(test_images) + 1  # num imgs + primary header

    cut1 = cutout_hdulist[1].data
    assert cut1.shape == (cutout_size, cutout_size)
    assert np.isnan(cut1[:cutout_size//2, :]).all()

    cutout_hdulist.close()

    # Test when cutout is in some images not others

    # Putting zeros into 2 images
    for i in range(2):
        hdu = fits.open(test_images[i], mode="update")
        hdu[0].data[:20, :] = 0
        hdu.flush()
        hdu.close()
        
        
    center_coord = SkyCoord("150.1163213 2.2007", unit='deg')
    cutout_file = cutouts.fits_cut(test_images, center_coord, cutout_size, single_outfile=True)
    
    cutout_hdulist = fits.open(cutout_file)
    assert len(cutout_hdulist) == len(test_images) + 1  # num imgs + primary header
    assert (cutout_hdulist[1].data == 0).all()
    assert (cutout_hdulist[2].data == 0).all()
    assert ~(cutout_hdulist[3].data == 0).any()
    assert ~(cutout_hdulist[4].data == 0).any()
    assert ~(cutout_hdulist[5].data == 0).any()
    assert ~(cutout_hdulist[6].data == 0).any()

    
    cutout_files = cutouts.fits_cut(test_images, center_coord, cutout_size, single_outfile=False)
    assert isinstance(cutout_files, list)
    assert len(cutout_files) == len(test_images) - 2
