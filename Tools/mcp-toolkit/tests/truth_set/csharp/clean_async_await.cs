using System.Threading.Tasks;
public class Good {
    public async Task<int> Run(Task<int> work) { return await work; }
}
