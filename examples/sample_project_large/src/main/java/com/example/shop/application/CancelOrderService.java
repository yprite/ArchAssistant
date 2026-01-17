package com.example.shop.application;

import com.example.shop.application.port.in.CancelOrderUseCase;
import com.example.shop.application.port.out.OrderRepositoryPort;
import com.example.shop.domain.model.Order;
import com.example.shop.domain.model.OrderId;
import org.springframework.stereotype.Service;

@Service
public class CancelOrderService implements CancelOrderUseCase {
    private final OrderRepositoryPort repository;

    public CancelOrderService(OrderRepositoryPort repository) {
        this.repository = repository;
    }

    @Override
    public void cancel(String orderId) {
        Order order = repository.findById(new OrderId(orderId));
        if (order != null) {
            repository.save(order);
        }
    }
}
