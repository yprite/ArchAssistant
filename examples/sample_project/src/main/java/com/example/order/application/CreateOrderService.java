package com.example.order.application;

import com.example.order.domain.Order;
import org.springframework.stereotype.Service;

@Service
public class CreateOrderService {
    private final Order order;

    public CreateOrderService(Order order) {
        this.order = order;
    }
}
