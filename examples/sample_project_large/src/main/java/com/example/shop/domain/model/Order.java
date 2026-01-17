package com.example.shop.domain.model;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public class Order {
    private final OrderId id;
    private final Customer customer;
    private final List<LineItem> items = new ArrayList<>();
    private OrderStatus status;
    private Instant createdAt;

    public Order(OrderId id, Customer customer) {
        this.id = id;
        this.customer = customer;
        this.status = OrderStatus.CREATED;
        this.createdAt = Instant.now();
    }

    public void addItem(LineItem item) {
        items.add(item);
    }

    public void markPaid() {
        this.status = OrderStatus.PAID;
    }

    public OrderId getId() {
        return id;
    }

    public Customer getCustomer() {
        return customer;
    }
}
