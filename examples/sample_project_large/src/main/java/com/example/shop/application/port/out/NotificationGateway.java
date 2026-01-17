package com.example.shop.application.port.out;

public interface NotificationGateway {
    void notifyCustomer(String customerId, String message);
}
