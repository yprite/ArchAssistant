package com.example.shop.adapter.inbound;

import com.example.shop.application.port.in.PlaceOrderCommand;
import com.example.shop.application.port.in.PlaceOrderUseCase;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {
    private final PlaceOrderUseCase useCase;

    public OrderController(PlaceOrderUseCase useCase) {
        this.useCase = useCase;
    }

    @PostMapping("/orders")
    public String placeOrder() {
        return useCase.place(new PlaceOrderCommand("customer-1", java.util.List.of("sku-1"))).value();
    }
}
