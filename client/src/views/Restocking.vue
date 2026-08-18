<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t("restocking.title") }}</h2>
      <p>{{ t("restocking.description") }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t("common.loading") }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-header">
          <span class="budget-label">{{ t("restocking.budget") }}</span>
          <span class="budget-value"
            >{{ currencySymbol }}{{ budget.toLocaleString() }}</span
          >
        </div>
        <input
          type="range"
          class="budget-slider"
          v-model.number="budget"
          min="5000"
          max="250000"
          step="2500"
        />
        <div class="budget-range-labels">
          <span>{{ currencySymbol }}5,000</span>
          <span>{{ currencySymbol }}250,000</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t("restocking.selectedItems") }}</div>
          <div class="stat-value">{{ selectedItems.length }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t("restocking.totalCost") }}</div>
          <div class="stat-value">
            {{ currencySymbol }}{{ totalCost.toLocaleString() }}
          </div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t("restocking.remaining") }}</div>
          <div class="stat-value">
            {{ currencySymbol }}{{ remaining.toLocaleString() }}
          </div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t("restocking.longestLeadTime") }}</div>
          <div class="stat-value">
            {{ maxLeadTime }} {{ t("restocking.days") }}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            {{ t("restocking.recommended") }} ({{ selectedItems.length }})
          </h3>
          <button
            class="btn-primary"
            :disabled="submitting || selectedItems.length === 0"
            @click="placeOrder"
          >
            {{ t("restocking.placeOrder") }}
          </button>
        </div>

        <div v-if="candidates.length === 0" class="empty-state">
          {{ t("restocking.noCandidates") }}
        </div>
        <div v-else-if="selectedItems.length === 0" class="empty-state">
          {{ t("restocking.noneAffordable") }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th class="col-check"></th>
                <th>{{ t("demand.table.sku") }}</th>
                <th>{{ t("demand.table.itemName") }}</th>
                <th>{{ t("orders.table.warehouse") }}</th>
                <th>{{ t("restocking.table.onHand") }}</th>
                <th>{{ t("demand.table.forecastedDemand") }}</th>
                <th>{{ t("restocking.table.shortfall") }}</th>
                <th>{{ t("restocking.table.unitCost") }}</th>
                <th>{{ t("restocking.table.orderQty") }}</th>
                <th>{{ t("restocking.table.lineCost") }}</th>
                <th>{{ t("restocking.table.leadTime") }}</th>
                <th>{{ t("restocking.table.urgency") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="candidate in affordable"
                :key="candidate.sku"
                :class="{ 'over-budget': candidate.skipped }"
              >
                <td class="col-check">
                  <input
                    type="checkbox"
                    :checked="candidate.selected"
                    :disabled="candidate.skipped"
                    @change="toggle(candidate.sku)"
                  />
                </td>
                <td>
                  <strong>{{ candidate.sku }}</strong>
                </td>
                <td>{{ candidate.name }}</td>
                <td>{{ candidate.warehouse }}</td>
                <td>{{ candidate.quantity_on_hand }}</td>
                <td>{{ candidate.forecasted_demand }}</td>
                <td>{{ candidate.shortfall }}</td>
                <td>
                  {{ currencySymbol }}{{ candidate.unit_cost.toLocaleString() }}
                </td>
                <td>{{ candidate.recommended_quantity }}</td>
                <td>
                  <strong
                    >{{ currencySymbol
                    }}{{ candidate.line_cost.toLocaleString() }}</strong
                  >
                </td>
                <td>
                  {{ candidate.lead_time_days }} {{ t("restocking.days") }}
                </td>
                <td>
                  <span :class="['badge', urgencyClass(candidate.urgency)]">
                    {{ candidate.urgency.toFixed(2) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="submitMessage" class="feedback-area success">
        {{ submitMessage }}
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from "vue";
import { api } from "../api";
import { useFilters } from "../composables/useFilters";
import { useI18n } from "../composables/useI18n";

export default {
  name: "Restocking",
  setup() {
    const { t, currentCurrency } = useI18n();
    const { selectedLocation, selectedCategory, getCurrentFilters } =
      useFilters();

    const currencySymbol = computed(() => {
      return currentCurrency.value === "JPY" ? "¥" : "$";
    });

    const loading = ref(true);
    const error = ref(null);
    const candidates = ref([]);
    const budget = ref(150000);
    const deselected = ref(new Set());
    const submitting = ref(false);
    const submitMessage = ref(null);

    // Greedy fill: walk candidates in server-provided urgency order, consuming
    // budget as we go. A user-deselected line frees its budget back up so a
    // later, cheaper line can move in. A line that doesn't fit is "skipped"
    // (shown but disabled) rather than dropped, since a later cheaper line
    // may still fit within the remaining budget.
    const affordable = computed(() => {
      let remaining = budget.value;
      return candidates.value.map((candidate) => {
        if (deselected.value.has(candidate.sku)) {
          return { ...candidate, selected: false, skipped: false };
        }
        if (candidate.line_cost <= remaining) {
          remaining -= candidate.line_cost;
          return { ...candidate, selected: true, skipped: false };
        }
        return { ...candidate, selected: false, skipped: true };
      });
    });

    const selectedItems = computed(() =>
      affordable.value.filter((c) => c.selected),
    );

    const totalCost = computed(() => {
      const sum = selectedItems.value.reduce(
        (total, c) => total + c.line_cost,
        0,
      );
      return Math.round(sum * 100) / 100;
    });

    const remaining = computed(() => budget.value - totalCost.value);

    const maxLeadTime = computed(() => {
      if (selectedItems.value.length === 0) return 0;
      return Math.max(...selectedItems.value.map((c) => c.lead_time_days));
    });

    const toggle = (sku) => {
      const next = new Set(deselected.value);
      if (next.has(sku)) {
        next.delete(sku);
      } else {
        next.add(sku);
      }
      deselected.value = next;
    };

    const urgencyClass = (urgency) => {
      if (urgency >= 1.0) return "danger";
      if (urgency >= 0.5) return "warning";
      return "info";
    };

    const loadCandidates = async () => {
      try {
        loading.value = true;
        error.value = null;
        const filters = getCurrentFilters();
        candidates.value = await api.getRestockCandidates({
          warehouse: filters.warehouse,
          category: filters.category,
        });
        deselected.value = new Set();
        submitMessage.value = null;
      } catch (err) {
        error.value = "Failed to load restocking candidates: " + err.message;
      } finally {
        loading.value = false;
      }
    };

    const placeOrder = async () => {
      if (submitting.value || selectedItems.value.length === 0) return;
      submitting.value = true;
      try {
        const result = await api.createRestockOrder({
          budget: budget.value,
          items: selectedItems.value.map((c) => ({
            sku: c.sku,
            quantity: c.recommended_quantity,
          })),
        });
        const deliveryDate = new Date(result.expected_delivery);
        const dateStr = isNaN(deliveryDate.getTime())
          ? result.expected_delivery
          : deliveryDate.toLocaleDateString();
        submitMessage.value = t("restocking.orderPlaced", {
          orderNumber: result.order_number,
          date: dateStr,
        });
      } catch (err) {
        error.value = "Failed to place restock order: " + err.message;
      } finally {
        submitting.value = false;
      }
    };

    // Inventory has no time dimension and order status is meaningless for a
    // purchase recommendation, so we only watch warehouse/category filters.
    watch([selectedLocation, selectedCategory], () => {
      loadCandidates();
    });

    onMounted(loadCandidates);

    return {
      t,
      currencySymbol,
      loading,
      error,
      candidates,
      budget,
      affordable,
      selectedItems,
      totalCost,
      remaining,
      maxLeadTime,
      toggle,
      urgencyClass,
      placeOrder,
      submitting,
      submitMessage,
    };
  },
};
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: none;
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: none;
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
}

.budget-slider:focus-visible {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.budget-range-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
}

.col-check {
  width: 40px;
  text-align: center;
}

.over-budget {
  opacity: 0.45;
}

.btn-primary {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.875rem;
}

.feedback-area {
  margin-top: 1.5rem;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
}

.feedback-area.success {
  background: #d1fae5;
  color: #059669;
  border: 1px solid #a7f3d0;
}
</style>
