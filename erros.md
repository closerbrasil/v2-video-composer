// ... existing code ...

### **Comandos Específicos para Respostas Explosivas**  

4. **`/debug -level=hardcore -error=logic_error -review_logs -terms=processos,logs,logica`**  
   Exemplo:  

   ```  
   /debug -level=hardcore -error=logic_error  
   Identifique onde o processo de validação de transações está mantendo estado incorreto entre execuções.  
   Revise os logs de 'ERR-407' para localizar a falha na sincronização de threads.  
   ```

5. **`/optimize -language=[sua_linguagem] -validation=strict -phases=identify,correct,review`**  
   Exemplo:  

   ```  
   /optimize -language=Java -validation=strict  
   Corrija o loop infinito no serviço de cache que persiste após atualizações.  
   Implemente verificação de estado consistente pós-correção usando checksums.  
   ```

// ... existing code ...

### **Exemplo Prático de Uso**  

**Seu Prompt**:  

```  
/debug -level=hardcore -error=state_mismatch -review_logs  
/optimize -language=Python -phases=identify,correct,review  
Processos mantêm estado anterior após reinicialização. Logs mostram 'WARN: State not reset'.  
Localize onde a reinicialização falha e implemente verificação em 3 estágios.  
```

**Resposta do DeepSeek-R1 (Modo Turbo)**:  

```python  
def reset_system_state():
    global system_state
    # Verificação tripla de estado
    with threading.Lock():
        old_state = system_state.copy()
        system_state = INITIAL_STATE
        if system_state == old_state:
            raise StatePersistanceError("Estado não reiniciado")
        log_verification(old_state, system_state)

def log_verification(old, new):
    logger.info(f"State reset verification: Old={old} New={new}")
    if any(old[k] == new[k] for k in old):
        logger.warning("Partial state persistence detected")
```

// ... existing code ...
