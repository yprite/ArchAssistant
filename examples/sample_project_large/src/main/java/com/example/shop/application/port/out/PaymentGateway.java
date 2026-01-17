package com.example.shop.application.port.out;

import com.example.shop.domain.model.Payment;

public interface PaymentGateway {
    void charge(Payment payment);
}
