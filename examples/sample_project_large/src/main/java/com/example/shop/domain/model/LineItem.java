package com.example.shop.domain.model;

public class LineItem {
    private final String sku;
    private final int quantity;
    private final Money price;

    public LineItem(String sku, int quantity, Money price) {
        this.sku = sku;
        this.quantity = quantity;
        this.price = price;
    }

    public Money subtotal() {
        return price.multiply(quantity);
    }
}
