package com.example.shop.application.port.in;

import java.util.List;

public class PlaceOrderCommand {
    public final String customerId;
    public final List<String> skus;

    public PlaceOrderCommand(String customerId, List<String> skus) {
        this.customerId = customerId;
        this.skus = skus;
    }
}
