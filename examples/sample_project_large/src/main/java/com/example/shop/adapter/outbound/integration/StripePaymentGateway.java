package com.example.shop.adapter.outbound.integration;

import com.example.shop.application.port.out.PaymentGateway;
import com.example.shop.domain.model.Payment;
import org.springframework.stereotype.Component;

@Component
public class StripePaymentGateway implements PaymentGateway {
    @Override
    public void charge(Payment payment) {
        // call Stripe
    }
}
