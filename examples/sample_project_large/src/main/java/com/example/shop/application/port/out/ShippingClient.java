package com.example.shop.application.port.out;

public interface ShippingClient {
    void scheduleShipment(String orderId);
}
