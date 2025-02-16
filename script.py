from functions.extract import fetch_article_content
from app import generate_audio, INSTRUCTION_TEMPLATES
import os
from dotenv import load_dotenv

def main():
    # Carrega as variáveis de ambiente
    load_dotenv()
    
    # Solicita a URL do artigo ao usuário
    print("\n=== Extrator de Artigo e Gerador de Podcast ===")
    url = input("\nDigite a URL do artigo: ").strip()
    
    print("\nExtraindo conteúdo do artigo...")
    # Extrai o conteúdo do artigo
    article = fetch_article_content(url)
    
    if not article:
        print("❌ Erro ao extrair o conteúdo do artigo.")
        return
    
    print("\n✅ Artigo extraído com sucesso!")
    print(f"\nTítulo: {article['title']}")
    
    # Prepara o texto para geração do podcast
    text_input = f"Título: {article['title']}\n\n{article['content']}"
    
    print("\nGerando podcast...")
    try:
        # Configurações para geração do podcast
        audio_file, transcript, original_text, error = generate_audio(
            text_input=text_input,
            pdf_files=None,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            text_model="o1-preview",
            audio_model="tts-1-hd",
            speaker_1_voice="alloy",
            speaker_2_voice="echo",
            api_base=None,
            intro_instructions=INSTRUCTION_TEMPLATES["podcast (Portuguese)"]["intro"],
            text_instructions=INSTRUCTION_TEMPLATES["podcast (Portuguese)"]["text_instructions"],
            scratch_pad_instructions=INSTRUCTION_TEMPLATES["podcast (Portuguese)"]["scratch_pad"],
            prelude_dialog=INSTRUCTION_TEMPLATES["podcast (Portuguese)"]["prelude"],
            podcast_dialog_instructions=INSTRUCTION_TEMPLATES["podcast (Portuguese)"]["dialog"],
            edited_transcript="",
            user_feedback="",
            language="Portuguese (Brazil)"
        )
        
        if error:
            print(f"\n❌ Erro ao gerar o podcast: {error}")
            return
            
        print("\n✅ Podcast gerado com sucesso!")
        print(f"\nArquivo de áudio salvo em: {audio_file}")
        print("\nTranscrição do podcast:")
        print("="*50)
        print(transcript)
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Erro ao gerar o podcast: {str(e)}")

if __name__ == "__main__":
    main()
