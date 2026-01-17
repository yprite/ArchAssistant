package com.example.shop.adapter.outbound.integration;

import com.example.shop.application.port.out.ShippingClient;
import org.springframework.stereotype.Component;

@Component
public class ShippingApiClient implements ShippingClient {
    @Override
    public void scheduleShipment(String orderId) {
        // call shipping api
    }
}
