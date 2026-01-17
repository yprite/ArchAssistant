package com.example.shop.domain.model;

import com.example.shop.domain.value.Money;

public class Payment {
    private final OrderId orderId;
    private final Money amount;
    private final String provider;

    public Payment(OrderId orderId, Money amount, String provider) {
        this.orderId = orderId;
        this.amount = amount;
        this.provider = provider;
    }
}
