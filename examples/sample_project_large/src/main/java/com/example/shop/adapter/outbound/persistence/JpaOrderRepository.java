package com.example.shop.adapter.outbound.persistence;

import com.example.shop.application.port.out.OrderRepositoryPort;
import com.example.shop.domain.model.Order;
import com.example.shop.domain.model.OrderId;
import org.springframework.stereotype.Repository;

@Repository
public class JpaOrderRepository implements OrderRepositoryPort {
    @Override
    public void save(Order order) {
        // persist
    }

    @Override
    public Order findById(OrderId id) {
        return null;
    }
}
