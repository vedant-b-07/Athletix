import express from 'express';
import {
    createOrder,
    getMyOrders,
    getOrderById,
    updateOrderStatus
} from '../controllers/orderController.js';

const router = express.Router();

router.post('/', createOrder);
router.get('/myorders/:uid', getMyOrders);
router.route('/:id').get(getOrderById);
router.put('/:id/status', updateOrderStatus);

export default router;
