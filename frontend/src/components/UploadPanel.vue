<script setup>
import { ref } from "vue";

defineProps({ busy: Boolean });
const emit = defineEmits(["files"]);
const dragging = ref(false);
const input = ref(null);

function choose(event) {
  const files = [...(event.target.files || [])];
  if (files.length) emit("files", files);
  event.target.value = "";
}

function drop(event) {
  dragging.value = false;
  const files = [...(event.dataTransfer?.files || [])];
  if (files.length) emit("files", files);
}
</script>

<template>
  <div
    class="upload-panel"
    :class="{ dragging, disabled: busy }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="drop"
  >
    <input
      ref="input"
      type="file"
      accept=".pdf,.txt,.md,.csv"
      multiple
      hidden
      @change="choose"
    />
    <div class="upload-icon">↥</div>
    <h3>Drop the pile here.</h3>
    <p>PDF, TXT, MD, or CSV · up to 5 MB each</p>
    <button
      class="button primary"
      type="button"
      :disabled="busy"
      @click="input.click()"
    >
      Choose files ↗
    </button>
    <small>Your files stay local until you ask AI to read them.</small>
  </div>
</template>
