/**
 * MCMC Callsign API
 * Fetches Malaysian amateur radio callsign data from GitHub releases.
 * 
 * Usage:
 *   <script src="https://YOUR_USERNAME.github.io/callsignscrapper/api.js"></script>
 *   <script>
 *     CallsignAPI.search('9M2').then(results => console.log(results));
 *   </script>
 */

(function (global) {
    // Configuration
    const REPO = 'bizkut/callsignscrapper';
    // Local file (works on GitHub Pages)
    const DATA_URL = './callsigns.json';
    // Fallback: GitHub release
    const DATA_URL_FALLBACK = `https://github.com/${REPO}/releases/download/latest/callsigns.json`;

    let cache = null;

    const API = {
        /**
         * Load all callsign data (cached after first load)
         * @returns {Promise<Object>} Full data object with assignments and metadata
         */
        async load() {
            if (cache) return cache;
            try {
                // Try jsDelivr first (CORS-friendly)
                const res = await fetch(DATA_URL);
                if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
                cache = await res.json();
            } catch (e) {
                // Fallback to direct GitHub release
                console.log('Trying fallback URL...');
                const res = await fetch(DATA_URL_FALLBACK);
                if (!res.ok) throw new Error(`Fallback failed: ${res.status}`);
                cache = await res.json();
            }
            return cache;
        },

        /**
         * Get all callsign assignments
         * @returns {Promise<Array>} Array of assignment objects
         */
        async getAll() {
            const data = await this.load();
            return data.assignments;
        },

        /**
         * Search callsigns by query (matches callsign, holder name, or assign number)
         * @param {string} query - Search query
         * @returns {Promise<Array>} Matching assignments
         */
        async search(query) {
            const data = await this.load();
            const q = query.toLowerCase().trim();
            if (!q) return [];
            return data.assignments.filter(a =>
                a.call_sign.toLowerCase().includes(q) ||
                a.assignment_holder.toLowerCase().includes(q) ||
                a.assign_no.toLowerCase().includes(q)
            );
        },

        /**
         * Get assignment by exact callsign
         * @param {string} callsign - Exact callsign (case-insensitive)
         * @returns {Promise<Object|null>} Assignment object or null
         */
        async getByCallsign(callsign) {
            const data = await this.load();
            return data.assignments.find(a =>
                a.call_sign.toLowerCase() === callsign.toLowerCase().trim()
            ) || null;
        },

        /**
         * Get assignments by prefix (e.g., '9M2', '9W')
         * @param {string} prefix - Callsign prefix
         * @returns {Promise<Array>} Matching assignments
         */
        async getByPrefix(prefix) {
            const data = await this.load();
            const p = prefix.toUpperCase().trim();
            return data.assignments.filter(a =>
                a.call_sign.toUpperCase().startsWith(p)
            );
        },

        /**
         * Get total count of assignments
         * @returns {Promise<number>} Total count
         */
        async getCount() {
            const data = await this.load();
            return data.assignments.length;
        },

        /**
         * Get metadata (last updated, etc.)
         * @returns {Promise<Object>} Metadata object
         */
        async getMetadata() {
            const data = await this.load();
            return data.metadata || {};
        },

        /**
         * Clear the cache to force fresh data on next load
         */
        clearCache() {
            cache = null;
        }
    };

    global.CallsignAPI = API;
})(typeof window !== 'undefined' ? window : global);
