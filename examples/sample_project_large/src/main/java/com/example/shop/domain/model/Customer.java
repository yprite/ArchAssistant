package com.example.shop.domain.model;

public class Customer {
    private final String id;
    private final String name;
    private final Address address;

    public Customer(String id, String name, Address address) {
        this.id = id;
        this.name = name;
        this.address = address;
    }

    public Address getAddress() {
        return address;
    }
}
