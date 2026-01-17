package com.example.shop.domain.model;

import java.util.UUID;

public class OrderId {
    private final String value;

    public OrderId() {
        this.value = UUID.randomUUID().toString();
    }

    public OrderId(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }
}
