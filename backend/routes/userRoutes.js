import express from 'express';
import {
    upsertUser,
    getUserProfile,
    updateUserProfile,
    getUserAddresses,
    addAddress,
    updateAddress,
    deleteAddress,
    setDefaultAddress
} from '../controllers/userController.js';

const router = express.Router();

router.post('/', upsertUser);
router.route('/:uid')
    .get(getUserProfile)
    .put(updateUserProfile);

// Addresses routes
router.route('/:uid/addresses')
    .get(getUserAddresses)
    .post(addAddress);

router.route('/:uid/addresses/:addressId')
    .put(updateAddress)
    .delete(deleteAddress);

router.put('/:uid/addresses/:addressId/default', setDefaultAddress);

export default router;
