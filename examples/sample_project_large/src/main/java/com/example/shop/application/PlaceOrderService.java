package com.example.shop.application;

import com.example.shop.application.port.in.PlaceOrderCommand;
import com.example.shop.application.port.in.PlaceOrderUseCase;
import com.example.shop.application.port.out.NotificationGateway;
import com.example.shop.application.port.out.OrderRepositoryPort;
import com.example.shop.application.port.out.PaymentGateway;
import com.example.shop.domain.model.Customer;
import com.example.shop.domain.model.Order;
import com.example.shop.domain.model.OrderId;
import com.example.shop.domain.model.Payment;
import com.example.shop.domain.value.Money;
import java.math.BigDecimal;
import org.springframework.stereotype.Service;

@Service
public class PlaceOrderService implements PlaceOrderUseCase {
    private final OrderRepositoryPort repository;
    private final PaymentGateway paymentGateway;
    private final NotificationGateway notificationGateway;

    public PlaceOrderService(
            OrderRepositoryPort repository,
            PaymentGateway paymentGateway,
            NotificationGateway notificationGateway
    ) {
        this.repository = repository;
        this.paymentGateway = paymentGateway;
        this.notificationGateway = notificationGateway;
    }

    @Override
    public OrderId place(PlaceOrderCommand command) {
        OrderId orderId = new OrderId();
        Customer customer = new Customer(command.customerId, "Guest", null);
        Order order = new Order(orderId, customer);
        repository.save(order);
        paymentGateway.charge(new Payment(orderId, new Money(BigDecimal.TEN), "stripe"));
        notificationGateway.notifyCustomer(command.customerId, "Order placed");
        return orderId;
    }
}
