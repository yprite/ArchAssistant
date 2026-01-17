package com.example.order.adapter.inbound;

import com.example.order.application.CreateOrderService;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {
    private final CreateOrderService service;

    public OrderController(CreateOrderService service) {
        this.service = service;
    }
}
