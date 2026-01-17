package com.example.shop.application.port.in;

import com.example.shop.domain.model.Order;

public interface GetOrderQuery {
    Order findById(String orderId);
}
