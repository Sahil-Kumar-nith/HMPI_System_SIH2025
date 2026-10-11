from .constants import STANDARD_LIMITS

def calculate_HPI(concentrations):
    """
    Calculate Heavy Metal Pollution Index (HPI)
    :param concentrations: dict {metal_name: concentration_value}
    :return: HPI value (float)
    """
    total_weighted_quality = 0
    total_weights = 0

    for metal, conc in concentrations.items():
        Si = STANDARD_LIMITS.get(metal)
        if Si is None:
            continue  # Skip metals without standards
        Wi = 1 / Si
        Qi = (conc / Si) * 100
        total_weighted_quality += Wi * Qi
        total_weights += Wi

    if total_weights == 0:
        return 0

    HPI = total_weighted_quality / total_weights
    return HPI

def analyze_sample(sample):
    limits = {
        'lead': 0.01,
        'mercury': 0.006,
        'cadmium': 0.003,
        'arsenic': 0.01,
    }

    unsafe_metals = []
    if sample.lead > limits['lead']:
        unsafe_metals.append('Lead')
    if sample.mercury > limits['mercury']:
        unsafe_metals.append('Mercury')
    if sample.cadmium > limits['cadmium']:
        unsafe_metals.append('Cadmium')
    if sample.arsenic > limits['arsenic']:
        unsafe_metals.append('Arsenic')

    is_drinkable = len(unsafe_metals) == 0

    # Suggest filters based on metals present
    suggested_filters = []
    if 'Lead' in unsafe_metals or 'Cadmium' in unsafe_metals or 'Arsenic' in unsafe_metals:
        suggested_filters.append('Reverse Osmosis')
    if 'Mercury' in unsafe_metals:
        suggested_filters.append('Activated Carbon Filter')

    return is_drinkable, suggested_filters
