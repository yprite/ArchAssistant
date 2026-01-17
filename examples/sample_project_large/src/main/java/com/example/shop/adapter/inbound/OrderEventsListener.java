package com.example.shop.adapter.inbound;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class OrderEventsListener {
    @KafkaListener(topics = "order-events")
    public void onMessage(String payload) {
        System.out.println(payload);
    }
}
