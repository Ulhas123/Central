// Fault injection state for CentraERP
const faults = {
  session_expiry: false,
  interstitial_banner: false,
  renamed_field: false,
  date_format_error: false,
  slow_response: false,
  lying_success: false,
  duplicate_trap: false
};

function getFaults() {
  return { ...faults };
}

function setFault(name, value) {
  if (name in faults) {
    faults[name] = Boolean(value);
    return true;
  }
  return false;
}

function resetFaults() {
  for (const k of Object.keys(faults)) {
    faults[k] = false;
  }
}

module.exports = {
  getFaults,
  setFault,
  resetFaults
};
