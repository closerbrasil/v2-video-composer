import os
from venv import logger
from openai import OpenAI
import subprocess
from pathlib import Path
import uuid
import tempfile
import shlex
import shutil
import time
import gradio as gr
import traceback
from PIL import Image
from PIL import ImageEnhance
import numpy as np
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, CompositeAudioClip, concatenate_audioclips, ImageSequenceClip, concatenate_videoclips
from PIL import ImageDraw
from PIL import ImageFilter

from functions.publicar_youtube import get_video_info
from functions.utils import get_files_infos
from functions.log_formatter import LogFormatter

# Supported models configuration
MODELS = {
    "deepseek-ai/DeepSeek-V3": {
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "Qwen/Qwen2.5-Coder-32B-Instruct": {
        "base_url": "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-Coder-32B-Instruct",
        "env_key": "HF_TOKEN",
    },
}

# Initialize client with DeepSeek model
client = OpenAI(
    base_url="https://api.deepseek.com/v1",
    api_key=os.environ["DEEPSEEK_API_KEY"],
)

# Inicializa o formatador de logs
log = LogFormatter()

def get_completion(prompt: str, files_info: list, top_p: float, temperature: float, model_choice: str) -> str:
    """Retorna um comando FFMPEG otimizado para criar vídeo com visualizador de áudio"""
    try:
        # Verifica se temos exatamente uma imagem e um áudio
        if len(files_info) != 2:
            raise ValueError("São necessários exatamente dois arquivos: uma imagem e um áudio")
            
        # Identifica qual arquivo é a imagem e qual é o áudio
        image_file = next((f for f in files_info if f["type"] == "image"), None)
        audio_file = next((f for f in files_info if f["type"] == "audio"), None)
        
        if not image_file or not audio_file:
            raise ValueError("Um arquivo de imagem e um de áudio são necessários")
            
        # Comando FFMPEG otimizado e mais leve
        command = (
            f"ffmpeg -loop 1 -i {image_file['name']} -i {audio_file['name']} "
            "-filter_complex \"[0:v]scale=1280:720:force_original_aspect_ratio=increase,"
            "crop=1280:720,setsar=1[bg];"
            "[1:a]showwaves=s=1280x120:mode=line:colors=white:rate=25[sw];"
            "[bg][sw]overlay=0:600\" "
            "-c:v libx264 -preset ultrafast -tune stillimage -crf 28 "
            "-c:a aac -b:a 128k -shortest -pix_fmt yuv420p -threads 4"
        )
        
        return command
        
    except Exception as e:
        print(f"❌ Erro ao gerar comando: {str(e)}")
        raise

def update(files, prompt, top_p=0.7, temperature=0.1, model_choice="deepseek-ai/DeepSeek-V3"):
    try:
        print("🎬 Gerando vídeo...")
        image_path, audio_path = files[0], files[1]
        
        # Verificação simplificada de arquivos
        for path in [image_path, audio_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        
        # Cria diretório de saída persistente
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        
        # Redimensiona a imagem para 1280x720 antes de processar
        print(log.process("Redimensionando imagem...", "🖼️"))
        temp_image = os.path.join(output_dir, "temp_resized.jpg")
        resized = resize_image(image_path)
        resized.save(temp_image, quality=95)
        print(log.success("Imagem redimensionada para 1280x720"))
        
        output_path = os.path.join(output_dir, f"output_{int(time.time())}.mp4")
        
        # Comando FFmpeg otimizado com visualizador de áudio melhorado
        ffmpeg_cmd = [
            'ffmpeg',
            '-loglevel', 'info',
            '-loop', '1',
            '-i', temp_image,
            '-i', audio_path,
            '-filter_complex',
            '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,setsar=1[bg];'
            '[1:a]showwaves=s=1280x180:mode=line:colors=white:rate=30:draw=full:scale=sqrt[sw];'
            '[bg][sw]overlay=(W-w)/2:270[v]',
            '-map', '[v]',
            '-map', '1:a',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'stillimage',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-y',
            output_path
        ]
        
        print(log.process("Executando FFmpeg...", "🎬"))
        result = subprocess.run(
            ffmpeg_cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            error_msg = f"Erro FFmpeg: {result.stderr}"
            print(log.error(error_msg))
            raise RuntimeError(error_msg)
            
        # Limpa arquivos temporários
        try:
            os.remove(temp_image)
        except:
            pass
            
        print(log.success("Vídeo gerado com sucesso"))
        return output_path
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        raise

def resize_image(image_path: str) -> Image.Image:
    """Redimensiona e processa a imagem para 1280x720 mantendo a proporção"""
    TARGET_SIZE = (1280, 720)
    
    img = Image.open(image_path).convert('RGB')
    width, height = img.size
    target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]
    
    # Calcula novo tamanho mantendo proporção
    if width/height > target_ratio:
        new_height = TARGET_SIZE[1]
        new_width = int(width * (new_height / height))
    else:
        new_width = TARGET_SIZE[0]
        new_height = int(height * (new_width / width))
    
    img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Crop centralizado
    left = (new_width - TARGET_SIZE[0])/2
    top = (new_height - TARGET_SIZE[1])/2
    right = left + TARGET_SIZE[0]
    bottom = top + TARGET_SIZE[1]
    
    img = img.crop((left, top, right, bottom))
    
    # Ajustes de imagem
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.1)
    
    return img

def test_resize_image(image_path: str, output_dir: str = "test_output"):
    """
    Testa o redimensionamento de uma imagem e salva o resultado para verificação.
    """
    try:
        # Cria diretório de teste se não existir
        os.makedirs(output_dir, exist_ok=True)
        
        # Processa a imagem
        print(f"\n🖼️ Testando redimensionamento da imagem: {image_path}")
        print(f"Dimensões originais: {Image.open(image_path).size}")
        
        # Redimensiona
        resized = resize_image(image_path)
        
        # Verifica dimensões
        if resized.size != (1280, 720):
            raise ValueError(f"Dimensões incorretas: {resized.size}")
            
        # Salva resultado
        output_path = os.path.join(output_dir, "test_resized.jpg")
        resized.save(output_path, quality=95)
        
        print(f"✅ Imagem redimensionada com sucesso!")
        print(f"Dimensões finais: {resized.size}")
        print(f"Resultado salvo em: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        raise e

def create_waveform_clip(audio_clip, waveform_height=180):
    """Cria visualização de onda de áudio usando MoviePy"""
    # Gerar dados da forma de onda
    audio_data = audio_clip.to_soundarray(fps=22050)
    if audio_data.ndim == 2:
        audio_data = audio_data.mean(axis=1)
    
    # Reduzir resolução para melhor performance
    step = max(1, len(audio_data) // 200)  # ~200 pontos por segundo
    audio_data = audio_data[::step]
    
    # Normalizar valores
    max_val = np.max(np.abs(audio_data))
    if max_val > 0:
        audio_data /= max_val
    
    # Criar frames da forma de onda
    duration = audio_clip.duration
    fps = 30
    frames = []
    
    for t in np.arange(0, duration, 1/fps):
        idx = int(t * len(audio_data) / duration)
        sample = audio_data[max(0, idx-5):idx+5]
        value = np.mean(np.abs(sample)) if len(sample) > 0 else 0
        
        # Criar imagem da forma de onda
        frame = Image.new('RGB', (1280, waveform_height), color='black')
        draw = ImageDraw.Draw(frame)
        
        # Desenhar linha central
        center_y = waveform_height // 2
        draw.line([(0, center_y), (1280, center_y)], fill='#404040', width=1)
        
        # Desenhar forma de onda
        x = int(1280 * (t / duration))
        height = int(value * (waveform_height - 20))
        draw.rectangle([x, center_y - height, x + 2, center_y + height], fill='white')
        
        frames.append(np.array(frame))
    
    return ImageSequenceClip(frames, fps=fps)

def compose_video(audio_path: str, image_path: str, output_path: str = None) -> str:
    """Compõe vídeo usando MoviePy"""
    try:
        # Verificar se a imagem existe, caso contrário usar imagem padrão
        if not os.path.exists(image_path):
            print("⚠️ Imagem não encontrada, usando imagem padrão...")
            image_path = "images/default.jpg"
            if not os.path.exists(image_path):
                from functions.create_default_image import create_default_image
                create_default_image()
        
        # Processar imagem
        resized_img = resize_image(image_path)
        img_clip = ImageClip(np.array(resized_img))
        
        # Processar áudio principal (narração)
        narration_clip = AudioFileClip(audio_path)
        
        # Processar áudio de fundo
        bg_audio = AudioFileClip("audios/bg-loop.mp3")
        
        # Ajustar duração do áudio de fundo
        if bg_audio.duration < narration_clip.duration:
            n_loops = int(np.ceil(narration_clip.duration / bg_audio.duration))
            bg_audio = concatenate_audioclips([bg_audio] * n_loops)
        bg_audio = bg_audio.subclip(0, narration_clip.duration)
        
        # Reduzir volume do áudio de fundo
        bg_audio = bg_audio.volumex(0.1)  # 10% do volume original
        
        # Combinar áudios
        final_audio = CompositeAudioClip([narration_clip, bg_audio])
        
        # Definir duração do clip de imagem
        img_clip = img_clip.set_duration(narration_clip.duration)
        
        # Criar forma de onda
        waveform_clip = create_waveform_clip(narration_clip)
        waveform_clip = waveform_clip.set_position(('center', img_clip.size[1] - waveform_clip.size[1]))
        
        # Combinar clips
        final_clip = CompositeVideoClip([img_clip, waveform_clip])
        final_clip.audio = final_audio
        
        # Configurações de exportação
        if not output_path:
            output_path = f"downloads/output_{int(time.time())}.mp4"
            
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=30,
            preset='ultrafast',
            threads=4,
            logger=None
        )
        
        # Limpar recursos
        narration_clip.close()
        bg_audio.close()
        final_audio.close()
        final_clip.close()
        
        return output_path
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        raise e

def get_video_duration(audio_path: str) -> str:
    """
    Calcula a duração do vídeo baseado no arquivo de áudio.
    
    Args:
        audio_path: Caminho do arquivo de áudio
        
    Returns:
        str: Duração formatada em minutos (ex: "3-4" ou "5")
    """
    try:
        audio_clip = AudioFileClip(audio_path)
        duration_minutes = audio_clip.duration / 60
        audio_clip.close()
        
        # Arredonda para o minuto mais próximo
        rounded_duration = round(duration_minutes)
        
        # Se a duração for menor que 1 minuto
        if rounded_duration < 1:
            return "1"
            
        # Se a duração for entre X e X.75 minutos, retorna "X"
        # Se for entre X.75 e X+1 minutos, retorna "X-Y"
        decimal_part = duration_minutes - int(duration_minutes)
        if decimal_part < 0.75:
            return str(int(duration_minutes))
        else:
            return f"{int(duration_minutes)}-{int(duration_minutes) + 1}"
            
    except Exception as e:
        print(f"⚠️ Erro ao calcular duração do vídeo: {str(e)}")
        return "3-5"  # Fallback padrão

def compose_vertical_video(video_path: str, thumbnail_path: str = None, output_path: str = None) -> str:
    """
    Converte um vídeo horizontal (1280x720) para formato vertical (1080x1920) para TikTok/Shorts.
    A imagem preencherá toda a tela vertical, sem bordas pretas.
    
    Args:
        video_path: Caminho do vídeo horizontal de entrada
        thumbnail_path: Caminho da thumbnail vertical (opcional)
        output_path: Caminho de saída do vídeo (opcional)
        
    Returns:
        str: Caminho do vídeo vertical gerado
    """
    try:
        # Define o caminho de saída na pasta downloads
        if not output_path:
            os.makedirs("downloads", exist_ok=True)
            output_path = os.path.join("downloads", f"vertical_output_{int(time.time())}.mp4")
        
        # Verifica se o upload de shorts está habilitado
        if os.getenv('ENABLE_SHORTS_UPLOAD', 'false').lower() != 'true':
            print("⚠️ Verticalização desabilitada (ENABLE_SHORTS_UPLOAD=false)")
            return None
            
        # Verifica a duração do vídeo
        probe = VideoFileClip(video_path)
        duration = probe.duration
        probe.close()
        
        if duration > 180:  # 3 minutos
            print(f"⚠️ Vídeo muito longo para verticalização: {duration:.1f}s (máximo 180s)")
            return None
        
        # Prepara o comando FFmpeg para preencher toda a tela vertical
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', video_path,
            '-t', '179',  # Limita a 2:59 (179 segundos)
            '-vf',
            'scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-c:a', 'aac',
            '-y',
            output_path
        ]
        
        # Executa o comando
        print("\n🎬 Convertendo para formato vertical...")
        result = subprocess.run(
            ffmpeg_cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Erro FFmpeg: {result.stderr}")
            
        print("✅ Vídeo vertical gerado com sucesso!")
        return output_path
        
    except Exception as e:
        print(f"❌ Erro ao criar vídeo vertical: {str(e)}")
        raise e

def create_vertical_thumbnail(image_path: str, output_path: str = None) -> str:
    """
    Converte uma imagem horizontal para formato vertical (1080x1920) para TikTok/Shorts.
    A imagem preencherá toda a tela vertical, com corte nas laterais se necessário.
    
    Args:
        image_path: Caminho da imagem horizontal de entrada
        output_path: Caminho de saída da imagem (opcional)
        
    Returns:
        str: Caminho da imagem vertical gerada
    """
    try:
        # Define o caminho de saída se não fornecido
        if not output_path:
            os.makedirs("downloads", exist_ok=True)
            output_path = os.path.join("downloads", f"vertical_thumb_{int(time.time())}.jpg")
            
        # Abre e redimensiona a imagem
        img = Image.open(image_path).convert('RGB')
        
        # Calcula as dimensões para preencher a tela vertical
        target_width = 1080
        target_height = 1920
        
        # Redimensiona a imagem mantendo a proporção e preenchendo toda a altura
        ratio = target_height / img.height
        new_width = int(img.width * ratio)
        
        # Redimensiona a imagem
        resized_img = img.resize((new_width, target_height), Image.LANCZOS)
        
        # Centraliza e corta as laterais
        left = (new_width - target_width) // 2
        right = left + target_width
        
        # Corta a imagem para o tamanho final
        vertical_img = resized_img.crop((left, 0, right, target_height))
        
        # Salva a imagem
        vertical_img.save(output_path, quality=95)
        
        return output_path
        
    except Exception as e:
        print(f"❌ Erro ao criar thumbnail vertical: {str(e)}")
        raise e

def add_thumbnail_as_first_frame(video_path: str, thumbnail_path: str, output_path: str = None) -> str:
    """
    Adiciona uma imagem como primeiro frame de um vídeo.
    
    Args:
        video_path: Caminho do vídeo original
        thumbnail_path: Caminho da thumbnail vertical
        output_path: Caminho de saída do vídeo (opcional)
        
    Returns:
        str: Caminho do vídeo com thumbnail adicionada
    """
    try:
        if not output_path:
            os.makedirs("downloads", exist_ok=True)
            output_path = os.path.join("downloads", f"with_thumb_{int(time.time())}.mp4")
            
        # Cria um vídeo de 1 segundo com a thumbnail
        thumb_clip = ImageClip(thumbnail_path).set_duration(1)
        
        # Carrega o vídeo original
        video_clip = VideoFileClip(video_path)
        
        # Concatena a thumbnail com o vídeo
        final_clip = concatenate_videoclips([thumb_clip, video_clip])
        
        # Exporta o vídeo final
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=30,
            preset='ultrafast',
            threads=4,
            logger=None
        )
        
        # Limpa recursos
        thumb_clip.close()
        video_clip.close()
        final_clip.close()
        
        return output_path
        
    except Exception as e:
        print(f"❌ Erro ao adicionar thumbnail como primeiro frame: {str(e)}")
        raise e