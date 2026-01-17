package com.example.shop.application;

import com.example.shop.application.port.out.PaymentGateway;
import com.example.shop.domain.model.Payment;
import org.springframework.stereotype.Service;

@Service
public class PaymentService {
    private final PaymentGateway paymentGateway;

    public PaymentService(PaymentGateway paymentGateway) {
        this.paymentGateway = paymentGateway;
    }

    public void charge(Payment payment) {
        paymentGateway.charge(payment);
    }
}
