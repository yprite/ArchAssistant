package com.example.shop.domain.model;

public class Address {
    private final String line1;
    private final String city;
    private final String country;

    public Address(String line1, String city, String country) {
        this.line1 = line1;
        this.city = city;
        this.country = country;
    }
}
