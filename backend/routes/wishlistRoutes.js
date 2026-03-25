import express from 'express';
import {
    getWishlist,
    addToWishlist,
    removeFromWishlist
} from '../controllers/wishlistController.js';

const router = express.Router();

router.route('/')
    .post(addToWishlist);

router.get('/:uid', getWishlist);
router.delete('/:uid/:productId', removeFromWishlist);

export default router;
