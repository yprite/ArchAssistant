package com.example.shop.application.port.in;

import com.example.shop.domain.model.OrderId;

public interface PlaceOrderUseCase {
    OrderId place(PlaceOrderCommand command);
}
