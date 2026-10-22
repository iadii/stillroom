<script setup>
import { displayDate, size } from "../api";

defineProps({ document: { type: Object, required: true }, selected: Boolean });
const emit = defineEmits(["select"]);
</script>

<template>
  <button
    class="document-row"
    :class="{ selected }"
    @click="emit('select', document)"
  >
    <span class="file-icon" :class="document.extension.slice(1)">{{
      document.extension.slice(1).toUpperCase()
    }}</span>
    <span class="file-summary"
      ><strong>{{ document.title || document.original_name }}</strong
      ><small
        >{{ document.original_name }} · {{ size(document.size_bytes) }}</small
      ><em
        >{{ document.category || "Waiting for analysis" }} <span>·</span>
        {{ displayDate(document.created_at) }}</em
      ></span
    >
    <span class="state" :class="document.state">{{
      document.state === "inbox"
        ? "New"
        : document.state === "archived"
          ? "Filed"
          : document.reviewed_at
            ? "Approved"
            : "Review"
    }}</span>
  </button>
</template>
