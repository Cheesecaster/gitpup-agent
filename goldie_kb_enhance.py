#!/usr/bin/env python3
"""Goldie KB Enhancement - Pattern matching and architectural insights from studied repos"""

import json, os, re
from difflib import SequenceMatcher

GITPUP = '/opt/gitpup'
DATA = os.path.join(GITPUP, 'data')
KB_FILE = os.path.join(DATA, 'knowledge.json')

def load_kb():
    """Load knowledge base"""
    try:
        with open(KB_FILE) as f:
            return json.load(f)
    except Exception as e:
        return {}

def extract_keywords(text, top_n=5):
    """Extract key technical terms from text"""
    # Common stopwords
    stops = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
             'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
             'should', 'may', 'might', 'must', 'shall', 'can', 'for', 'and', 'nor',
             'but', 'or', 'yet', 'so', 'in', 'on', 'at', 'to', 'from', 'by', 'with',
             'about', 'of', 'as', 'make', 'build', 'create', 'write', 'implement',
             'code', 'system', 'application', 'program', 'script', 'this', 'that'}
    
    # Split and clean
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', text.lower())
    
    # Filter stopwords and short words
    filtered = [w for w in words if w not in stops and len(w) > 2]
    
    # Count frequency
    freq = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    
    # Sort by frequency
    return sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]

def find_patterns(keywords, top_n=5):
    """Find relevant patterns from studied repos"""
    kb = load_kb()
    if not kb:
        return []
    
    results = []
    repos = kb.get('repos', {})
    
    for repo_name, repo_data in repos.items():
        study_level = repo_data.get('study_level', 0)
        if study_level < 2:
            continue  # Skip shallow studies
        
        patterns = repo_data.get('patterns', [])
        insights = repo_data.get('insights', [])
        best_practices = repo_data.get('best_practices', [])
        
        # Score relevance
        score = 0
        matched_terms = []
        
        all_text = ' '.join(patterns + insights + best_practices + [repo_name]).lower()
        
        for kw, weight in keywords:
            if kw.lower() in all_text:
                score += weight * (study_level / 4.0)  # Weight by study depth
                matched_terms.append(kw)
        
        if score > 0:
            results.append({
                'repo': repo_name,
                'study_level': study_level,
                'score': score,
                'matched_terms': matched_terms,
                'patterns': patterns[:3],  # Top 3 patterns
                'insights': insights[:2],  # Top 2 insights
                'best_practices': best_practices[:2]  # Top 2 practices
            })
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]

def get_architectural_decisions(keywords):
    """Extract architectural decisions relevant to keywords"""
    kb = load_kb()
    if not kb:
        return []
    
    decisions = []
    repos = kb.get('repos', {})
    
    for repo_name, repo_data in repos.items():
        study_level = repo_data.get('study_level', 0)
        if study_level < 3:
            continue  # Need deep study for architectural insights
        
        insights = repo_data.get('insights', [])
        patterns = repo_data.get('patterns', [])
        
        all_text = ' '.join(insights + patterns + [repo_name]).lower()
        
        # Check keyword relevance
        relevant = any(kw.lower() in all_text for kw, _ in keywords)
        if not relevant:
            continue
        
        for insight in insights:
            if any(kw.lower() in insight.lower() for kw, _ in keywords):
                decisions.append({
                    'repo': repo_name,
                    'insight': insight,
                    'source': 'deep_study'
                })
    
    return decisions[:5]

def compare_approaches(keywords):
    """Compare different approaches from studied repos"""
    kb = load_kb()
    if not kb:
        return []
    
    approaches = []
    repos = kb.get('repos', {})
    
    for repo_name, repo_data in repos.items():
        study_level = repo_data.get('study_level', 0)
        if study_level < 2:
            continue
        
        patterns = repo_data.get('patterns', [])
        if not patterns:
            continue
        
        all_text = ' '.join(patterns + [repo_name]).lower()
        
        # Check keyword relevance
        relevant = any(kw.lower() in all_text for kw, _ in keywords)
        if not relevant:
            continue
        
        # Primary pattern (first one)
        primary = patterns[0] if patterns else None
        if primary:
            approaches.append({
                'repo': repo_name,
                'approach': primary,
                'source': f'study_level_{study_level}'
            })
    
    return approaches[:5]

def enhance_context(task_description):
    """Enhance task with KB insights"""
    keywords = extract_keywords(task_description)
    
    if not keywords:
        return {}
    
    patterns = find_patterns(keywords, top_n=3)
    decisions = get_architectural_decisions(keywords)
    approaches = compare_approaches(keywords)
    
    return {
        'keywords': [kw for kw, _ in keywords],
        'patterns': patterns,
        'decisions': decisions,
        'approaches': approaches,
        'pattern_count': len(patterns),
        'decision_count': len(decisions)
    }

def format_kb_context(enrichment):
    """Format KB enrichment for LLM prompt"""
    if not enrichment or not enrichment.get('patterns'):
        return ""
    
    lines = []
    lines.append("\n## Relevant Patterns from Studied Repositories\n")
    
    for i, p in enumerate(enrichment.get('patterns', []), 1):
        repo = p['repo']
        level = p['study_level']
        lines.append(f"{i}. **{repo}** (study level {level}/4)")
        
        # Add patterns
        for pattern in p.get('patterns', [])[:2]:
            lines.append(f"   • Pattern: {pattern[:150]}")
        
        # Add insights
        for insight in p.get('insights', [])[:1]:
            lines.append(f"   • Insight: {insight[:150]}")
        
        # Add best practices
        for bp in p.get('best_practices', [])[:1]:
            lines.append(f"   • Best Practice: {bp[:150]}")
    
    # Add architectural decisions
    if enrichment.get('decisions'):
        lines.append("\n## Architectural Decisions\n")
        for d in enrichment.get('decisions', [])[:3]:
            lines.append(f"• From **{d['repo']}**: {d['insight']}")
    
    # Add approach comparisons
    if enrichment.get('approaches'):
        lines.append("\n## Approach Comparisons\n")
        for a in enrichment.get('approaches', [])[:3]:
            lines.append(f"• **{a['repo']}**: {a['approach']}")
    
    return '\n'.join(lines)
