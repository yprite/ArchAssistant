package com.example.shop.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class OrderEntity {
    @Id
    private String id;
    private String customerId;
    private String status;
}
