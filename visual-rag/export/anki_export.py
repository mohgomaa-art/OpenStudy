import os
import hashlib
import genanki
import config

def get_deterministic_id(text: str) -> int:
    """Generates a stable 31-bit integer ID from a string using MD5."""
    return int(hashlib.md5(text.encode('utf-8')).hexdigest()[:8], 16) & 0x7FFFFFFF

# CSS styling for Anki cards matching our visual-rag dark aesthetic
ANKI_CARD_STYLE = """
.card {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 19px;
    text-align: center;
    color: #f4f4f5;
    background-color: #09090b;
    padding: 30px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}
.front-label {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.1em;
    color: #a78bfa;
    margin-bottom: 20px;
    text-transform: uppercase;
}
.back-label {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.1em;
    color: #ec4899;
    margin-bottom: 20px;
    text-transform: uppercase;
}
.tag-badge {
    display: inline-block;
    font-size: 11px;
    color: #8b5cf6;
    background: rgba(139, 92, 246, 0.1);
    border: 1px solid rgba(139, 92, 246, 0.2);
    padding: 3px 8px;
    border-radius: 4px;
    margin-top: 25px;
}
"""

def export_to_anki(flashcard_json: dict, output_apkg_path: str = None) -> str:
    """
    Converts flashcard JSON into an importable Anki (.apkg) deck file.
    Deterministic IDs ensure stable deck overrides on re-imports.
    """
    title = flashcard_json.get("title", "Visual RAG Flashcards")
    cards_list = flashcard_json.get("cards", [])
    
    # Generate deterministic IDs for model and deck
    model_id = get_deterministic_id(title + "_model_v1")
    deck_id = get_deterministic_id(title + "_deck_v1")
    
    # Define Anki Card Model (Front/Back)
    my_model = genanki.Model(
        model_id,
        'Visual RAG Study Model',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
            {'name': 'Tag'},
        ],
        templates=[
            {
                'name': 'Visual Card',
                'qfmt': '<div class="front-label">Concept / Question</div><div>{{Front}}</div>',
                'afmt': '{{FrontSide}}<hr id="answer"><div class="back-label">Explanation / Answer</div><div style="font-size: 16px; line-height: 1.5; color: #d4d4d8;">{{Back}}</div><br><span class="tag-badge">{{Tag}}</span>',
            },
        ],
        css=ANKI_CARD_STYLE
    )
    
    # Create Deck
    my_deck = genanki.Deck(deck_id, title)
    
    # Add Cards
    for card in cards_list:
        front = card.get("front", "")
        back = card.get("back", "")
        tag = card.get("tag", "General")
        
        note = genanki.Note(
            model=my_model,
            fields=[front, back, tag]
        )
        my_deck.add_note(note)
        
    # Save package
    if not output_apkg_path:
        safe_title = "".join([c if c.isalnum() else "_" for c in title.replace(" ", "_")])[:30]
        output_apkg_path = os.path.join(config.OUTPUT_DIR, f"{safe_title}.apkg")
        
    os.makedirs(os.path.dirname(output_apkg_path), exist_ok=True)
    
    genanki.Package(my_deck).write_to_file(output_apkg_path)
    print(f"[Anki Export] Saved Anki deck package: {output_apkg_path}")
    return output_apkg_path
