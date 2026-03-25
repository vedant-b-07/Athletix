import express from 'express';
import {
    getCart,
    addToCart,
    updateCartItem,
    removeFromCart,
    clearCart
} from '../controllers/cartController.js';

const router = express.Router();

router.route('/')
    .post(addToCart);

router.get('/:uid', getCart);
router.delete('/clear/:uid', clearCart);
router.route('/:id')
    .put(updateCartItem)
    .delete(removeFromCart);

export default router;
