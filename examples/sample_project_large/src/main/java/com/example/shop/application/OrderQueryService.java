package com.example.shop.application;

import com.example.shop.application.port.in.GetOrderQuery;
import com.example.shop.application.port.out.OrderRepositoryPort;
import com.example.shop.domain.model.Order;
import com.example.shop.domain.model.OrderId;
import org.springframework.stereotype.Service;

@Service
public class OrderQueryService implements GetOrderQuery {
    private final OrderRepositoryPort repository;

    public OrderQueryService(OrderRepositoryPort repository) {
        this.repository = repository;
    }

    @Override
    public Order findById(String orderId) {
        return repository.findById(new OrderId(orderId));
    }
}
