# Final Spatial Support Methodology — 300 m Maximum Radius

## 1. Purpose

The spatial support radius defines the maximum distance over which an eligible Outdoor pedestrian sensor may contribute evidence to a walking-route location.

It does not mean pedestrian conditions are uniform inside a 300 m circle.

It is a project-specific support limit, not a universal urban-planning or clinical threshold.

---

## 2. Original Sensor-Spacing Evidence

The outdoor sensor network showed:

| Statistic | Nearest-neighbour distance |
|---|---:|
| P25 | 46.47 m |
| Median | 86.48 m |
| P75 | 168.20 m |
| P90 | 243.51 m |
| P95 | 276.18 m |
| P99 | 452.95 m |
| Maximum | 458.52 m |

Approximately 95% of Outdoor sensors had another Outdoor sensor within 300 m.

The >300 m tail was driven by a small number of isolated sensors.

---

## 3. Original Radius Decision

The initial leave-one-sensor-out radius analysis showed that 300 m provided a strong coverage/locality compromise.

The project rejected the automatically favoured 475 m option because a local pedestrian environment should not be smoothed over nearly half a kilometre simply to maximise numerical coverage.

The operational radius was therefore set to:

```text
MAX_SPATIAL_SUPPORT_RADIUS_M = 300
CORE_SPATIAL_SUPPORT_RADIUS_M = 250
```

---

## 4. Final V1B Validation on the Final Crowd Target

V1B re-ran the spatial experiment using the final primary Crowd Exposure target:

```text
Network percentile
```

At 300 m:

| Method | Coverage | MAE | RMSE | Median AE |
|---|---:|---:|---:|---:|
| **1/d** | 92.98% | **17.2364** | **21.9956** | 14.1196 |
| Gaussian150 | 92.98% | 17.3453 | 22.1058 | 14.3178 |
| Equal | 92.98% | 17.5218 | 22.3740 | 14.4313 |
| 1/d² | 92.98% | 17.5362 | 22.4895 | **14.0273** |
| Nearest | 92.98% | 18.7329 | 24.3699 | 14.4892 |

Unlike the earlier V1 result, this V1B result directly tests the final Network target.

Therefore the final spatial weighting is:

```text
inverse distance
1 / d
```

---

## 5. Final Radius Trade-off Using 1/d

### 250 m

```text
coverage = 87.73%
MAE = 17.0623
RMSE = 21.9694
```

### 300 m

```text
coverage = 92.98%
MAE = 17.2364
RMSE = 21.9956
```

### 475 m

```text
coverage = 99.59%
MAE = 16.7946
RMSE = 21.0813
```

The 475 m result has better numerical error and almost complete network redundancy.

However, compared with 300 m:

```text
radius increase:
175 m

relative radius increase:
58.3%

coverage gain:
about 6.61 percentage points
```

The project intentionally does not optimise only for cross-validation coverage.

For sensory-sensitive walking-route support, locality matters: a sensor hundreds of metres away can be separated by multiple intersections, pedestrian corridors and activity generators.

The retained datasets do not contain enough street-network/built-environment information to prove that 475 m remains locally representative.

Therefore:

> 300 m remains the final maximum support radius even though a larger radius can reduce cross-validation error.

This is a deliberate **locality-constrained modelling decision**.

---

## 6. Final Spatial Rule

```text
nearest valid eligible Outdoor sensor <= 250 m
→ SUPPORTED

250 m < nearest valid eligible Outdoor sensor <= 300 m
→ LIMITED

nearest valid eligible Outdoor sensor > 300 m
or no valid sensor score within 300 m
→ NO_DATA
```

---

## 7. Final Weighting Formula

For valid supporting sensors:

\[
w_i = \frac{1}{\max(d_i, 1)}
\]

\[
S(x,t) =
\frac{\sum_i w_i P_{i,t}}
{\sum_i w_i}
\]

where:

- \(d_i\) = distance from target point to sensor \(i\), in metres;
- \(P_{i,t}\) = the sensor's already-normalised percentile score;
- only valid eligible sensors inside 300 m are included.

The one-metre floor prevents division by zero at a sensor coordinate.

---

## 8. Dense Sensor Areas

Do not:

```text
sum raw counts from all nearby sensors
```

because dense sensor deployment would then mechanically inflate the estimate.

Instead:

```text
normalise each sensor to the required percentile metric
→ apply 1/d weighting
→ normalise the weights
```

More nearby sensors increase evidence, not raw crowd magnitude.

---

## 9. Sparse Sensor Areas

Do not:

```text
keep increasing the search radius until a sensor is found
```

If no valid eligible sensor is within 300 m:

```text
NO_DATA
```

This prevents false reassurance in poorly monitored areas.

---

## 10. POI Coverage Evidence

V6 applied the final 250/300 m coverage rule to 242 landmarks/POIs:

| Status | Count | Percentage |
|---|---:|---:|
| Supported | 114 | 47.11% |
| Limited | 11 | 4.55% |
| No Data | 117 | 48.35% |

This is POI coverage only.

It is not route coverage and not CBD land-area coverage.

---

## 11. Final Implementation Parameters

```text
MAX_SPATIAL_SUPPORT_RADIUS_M=300
CORE_SPATIAL_SUPPORT_RADIUS_M=250
SPATIAL_WEIGHT_METHOD=inverse_distance
SPATIAL_WEIGHT_POWER=1
SPATIAL_DISTANCE_FLOOR_M=1
```

---

## 12. Final Status

| Decision | Status |
|---|---|
| Maximum radius = 300 m | **Final / adopted** |
| Core support = 250 m | **Final / adopted** |
| >300 m = No Data | **Final / adopted** |
| Weighting = 1/d | **Final / confirmed by V1B** |
| Raw-count spatial summation | **Rejected** |
| Unbounded extrapolation | **Rejected** |

No further radius/weighting validation is required for the MVP.
