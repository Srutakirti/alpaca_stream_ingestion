package com.example.kstreams;

import com.fasterxml.jackson.annotation.JsonProperty;

public class StockData {
    @JsonProperty("T")
    private String T;

    @JsonProperty("S")
    private String S;

    @JsonProperty("o")
    private double o;

    @JsonProperty("h")
    private double h;

    @JsonProperty("l")
    private double l;

    @JsonProperty("c")
    private double c;

    @JsonProperty("v")
    private long v;

    @JsonProperty("t")
    private String t;

    @JsonProperty("n")
    private int n;

    @JsonProperty("vw")
    private double vw;

    // Default constructor for Jackson
    public StockData() {
    }

    // Getters and setters
    @JsonProperty("T")
    public String getT() {
        return T;
    }

    @JsonProperty("T")
    public void setT(String t) {
        T = t;
    }

    @JsonProperty("S")
    public String getS() {
        return S;
    }

    @JsonProperty("S")
    public void setS(String s) {
        S = s;
    }

    @JsonProperty("o")
    public double getO() {
        return o;
    }

    @JsonProperty("o")
    public void setO(double o) {
        this.o = o;
    }

    @JsonProperty("h")
    public double getH() {
        return h;
    }

    @JsonProperty("h")
    public void setH(double h) {
        this.h = h;
    }

    @JsonProperty("l")
    public double getL() {
        return l;
    }

    @JsonProperty("l")
    public void setL(double l) {
        this.l = l;
    }

    @JsonProperty("c")
    public double getC() {
        return c;
    }

    @JsonProperty("c")
    public void setC(double c) {
        this.c = c;
    }

    @JsonProperty("v")
    public long getV() {
        return v;
    }

    @JsonProperty("v")
    public void setV(long v) {
        this.v = v;
    }

    @JsonProperty("timestamp")
    public String getT_timestamp() {
        return t;
    }

    @JsonProperty("t")
    public void setT_timestamp(String t) {
        this.t = t;
    }

    @JsonProperty("n")
    public int getN() {
        return n;
    }

    @JsonProperty("n")
    public void setN(int n) {
        this.n = n;
    }

    @JsonProperty("vw")
    public double getVw() {
        return vw;
    }

    @JsonProperty("vw")
    public void setVw(double vw) {
        this.vw = vw;
    }

    @Override
    public String toString() {
        return "StockData{" +
                "T='" + T + '\'' +
                ", S='" + S + '\'' +
                ", o=" + o +
                ", h=" + h +
                ", l=" + l +
                ", c=" + c +
                ", v=" + v +
                ", timestamp='" + t + '\'' +
                ", n=" + n +
                ", vw=" + vw +
                '}';
    }
}
