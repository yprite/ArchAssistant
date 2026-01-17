package com.example.shop.adapter.outbound.integration;

import com.example.shop.application.port.out.NotificationGateway;
import org.springframework.stereotype.Component;

@Component
public class EmailNotificationAdapter implements NotificationGateway {
    @Override
    public void notifyCustomer(String customerId, String message) {
        // send email
    }
}
