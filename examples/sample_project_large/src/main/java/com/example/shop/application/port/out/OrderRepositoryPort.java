package com.example.shop.application.port.out;

import com.example.shop.domain.model.Order;
import com.example.shop.domain.model.OrderId;

public interface OrderRepositoryPort {
    void save(Order order);
    Order findById(OrderId id);
}
