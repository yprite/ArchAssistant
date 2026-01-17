package com.example.shop.adapter.inbound;

import com.example.shop.application.port.in.CancelOrderUseCase;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AdminOrderController {
    private final CancelOrderUseCase cancelOrderUseCase;

    public AdminOrderController(CancelOrderUseCase cancelOrderUseCase) {
        this.cancelOrderUseCase = cancelOrderUseCase;
    }

    @DeleteMapping("/admin/orders")
    public void cancel() {
        cancelOrderUseCase.cancel("order-1");
    }
}
